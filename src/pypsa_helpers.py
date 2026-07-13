import pandas as pd


def solve_scenario(network, co2_limit=None, solver_name="highs", time_limit=3600, solver="ipm", run_crossover=False, ipm_optimality_tolerance=1e-8):
    network = network.copy()
    if co2_limit is not None:
        network.add(
            "GlobalConstraint",
            "co2_limit",
            type="primary_energy",
            carrier_attribute="co2_emissions",
            sense="<=",
            constant=co2_limit,
        )
    # time_limit (seconds): HiGHS returns its best solution found so far instead of
    # running indefinitely if the LP struggles to converge. solver="ipm" (interior-point)
    # instead of the default dual simplex: simplex was stalling on persistent primal
    # infeasibility for this large, mildly-degenerate capacity-expansion LP.
    #
    # run_crossover=False: IPM alone reaches an excellent solution (gap ~1e-12) in a
    # fraction of the time, but HiGHS's crossover step (converting that to an exact basic
    # solution) sometimes reports "imprecise" and falls back to a dual-simplex cleanup
    # that can run for hours, blowing straight past time_limit (observed: 1137s for IPM
    # alone vs. 7662s total once a bad crossover kicked in). We don't need an exact vertex
    # solution for reporting capacities/dispatch, so skip crossover entirely.
    #
    # ipm_optimality_tolerance: keep at the default (1e-8). Tried loosening to 1e-3 to
    # save time - don't: HiGHS separately checks the P-D objective error against its own
    # fixed 1e-7 tolerance regardless of this setting, so a looser value here just makes
    # HiGHS downgrade the result to "Unknown" after the fact, wasting the whole solve.
    status, condition = network.optimize(
        solver_name=solver_name,
        solver_options={
            "time_limit": time_limit,
            "solver": solver,
            "run_crossover": "off" if not run_crossover else "on",
            "ipm_optimality_tolerance": ipm_optimality_tolerance,
        },
    )
    network.meta["status"] = status
    network.meta["termination_condition"] = condition
    return network


def require_optimal(network):
    """Raise if the solve didn't actually reach optimality.

    When HiGHS stops early (e.g. termination_condition == "time_limit"), PyPSA still
    populates p_nom_opt/dispatch with the solver's current (pre-crossover) iterate, but
    that iterate is not yet primal-feasible and network.objective silently reads back as
    0.0. Reading cost/CO2 numbers off a non-optimal solve looks like "zero cost" or "the
    CO2 cap didn't work" when actually the solve just never finished - refuse to proceed
    instead of reporting those misleading numbers.
    """
    condition = network.meta.get("termination_condition")
    if condition != "optimal":
        raise RuntimeError(
            f"Solve did not reach optimality (termination_condition={condition!r}). "
            "network.objective and any cost/CO2 numbers derived from this solve are not "
            "reliable - increase time_limit (or reduce problem size) and re-solve."
        )


def total_co2(network):
    dispatch = network.generators_t.p
    weighting = network.snapshot_weightings.generators
    em_per_mwh = network.generators.carrier.map(network.carriers.co2_emissions)
    return dispatch.mul(weighting, axis=0).mul(em_per_mwh, axis=1).sum().sum()


def scale_capital_cost(network, carrier, fraction):
    """Return a copy of network with capital_cost scaled by `fraction` for every
    Generator/Link/StorageUnit/Store whose carrier matches `carrier`. Used for technology
    cost sensitivity sweeps (e.g. electrolysis capital cost at 100/75/50/25/0%)."""
    network = network.copy()
    for component in ["generators", "links", "storage_units", "stores"]:
        df = getattr(network, component)
        mask = df.carrier == carrier
        df.loc[mask, "capital_cost"] = df.loc[mask, "capital_cost"] * fraction
    return network


def total_system_cost(network, cost_scale=1):
    """Total annualized system cost (EUR/yr), computed directly from capacities and
    dispatch rather than trusting network.objective (see require_optimal)."""
    weighting = network.snapshot_weightings.generators

    capital = 0.0
    capital += (network.generators.capital_cost * network.generators.p_nom_opt).sum()
    capital += (network.storage_units.capital_cost * network.storage_units.p_nom_opt).sum()
    capital += (network.links.capital_cost * network.links.p_nom_opt).sum()
    capital += (network.stores.capital_cost * network.stores.e_nom_opt).sum()

    marginal = (
        network.generators_t.p.mul(weighting, axis=0)
        .mul(network.generators.marginal_cost, axis=1)
        .sum()
        .sum()
    )

    return (capital + marginal) * cost_scale


def cost_by_technology(network, cost_scale=1):
    """Annualized system cost (EUR/yr) per carrier, split into capital and marginal cost."""
    weighting = network.snapshot_weightings.generators

    capital = pd.Series(dtype=float)
    for component, nom_attr in [
        ("generators", "p_nom_opt"),
        ("storage_units", "p_nom_opt"),
        ("links", "p_nom_opt"),
        ("stores", "e_nom_opt"),
    ]:
        df = getattr(network, component)
        cost = (df.capital_cost * df[nom_attr]).groupby(df.carrier).sum()
        capital = capital.add(cost, fill_value=0)

    marginal = (
        network.generators_t.p.mul(weighting, axis=0)
        .mul(network.generators.marginal_cost, axis=1)
        .sum()
        .groupby(network.generators.carrier)
        .sum()
    )

    breakdown = pd.DataFrame({"capital_cost": capital, "marginal_cost": marginal}).fillna(0)
    return breakdown * cost_scale


def capacity_by_technology(network):
    """Optimal built capacity per carrier (MW for generators/links/storage_units, MWh for
    stores), across all component types."""
    capacities = pd.Series(dtype=float)
    for component, nom_attr in [
        ("generators", "p_nom_opt"),
        ("storage_units", "p_nom_opt"),
        ("links", "p_nom_opt"),
        ("stores", "e_nom_opt"),
    ]:
        df = getattr(network, component)
        capacities = capacities.add(df.groupby("carrier")[nom_attr].sum(), fill_value=0)
    return capacities


def generation_by_technology(network):
    """Actual annual energy delivered to the grid (MWh/yr) per carrier - the dispatch-side
    counterpart to capacity_by_technology's nameplate MW. Idle installed capacity (e.g. an
    existing CCGT fleet forced to zero by a CO2 cap) reads as zero here even though it still
    counts as capacity there. Same demand-covering set as capacity_by_technology's
    power_capacity_table (generators, battery discharge, H2 fuel cell output) - excludes H2
    electrolysis (a load, not a source) and H2 store (energy, not power) since neither
    delivers electricity to the grid; also excludes AC (transmission moves energy, it
    doesn't generate it)."""
    weighting = network.snapshot_weightings.generators

    generation = (
        network.generators_t.p.clip(lower=0)
        .mul(weighting, axis=0)
        .sum()
        .groupby(network.generators.carrier)
        .sum()
    )

    battery_discharge = (
        network.storage_units_t.p.clip(lower=0)
        .mul(weighting, axis=0)
        .sum()
        .groupby(network.storage_units.carrier)
        .sum()
    )

    result = generation.add(battery_discharge, fill_value=0)

    fc_links = network.links[network.links.carrier == "H2 fuel cell"].index
    if len(fc_links):
        fc_output = (-network.links_t.p1[fc_links]).clip(lower=0).mul(weighting, axis=0).sum().sum()
        result = result.add(pd.Series({"H2 fuel cell": fc_output}), fill_value=0)

    return result


def electricity_mix(network):
    """Share of total electricity generation (%) by carrier."""
    weighting = network.snapshot_weightings.generators
    generation = (
        network.generators_t.p.clip(lower=0)
        .mul(weighting, axis=0)
        .sum()
        .groupby(network.generators.carrier)
        .sum()
    )
    return generation / generation.sum() * 100


def co2_shadow_price(network, cost_scale=1):
    """EUR/tCO2 shadow price of the co2_limit GlobalConstraint (None if not present)."""
    if "co2_limit" not in network.global_constraints.index:
        return None
    return abs(network.global_constraints.loc["co2_limit", "mu"]) * cost_scale


def curtailment_rate(network, carriers=("onwind", "solar")):
    """Curtailment rate (%) per carrier: (available - dispatched) / available, summed
    over the year."""
    gens = network.generators[network.generators.carrier.isin(carriers)]
    available = (network.generators_t.p_max_pu[gens.index] * gens.p_nom_opt).clip(lower=1e-9)
    dispatched = network.generators_t.p[gens.index]
    curtailed = (available - dispatched).clip(lower=0)

    per_carrier_curtailed = curtailed.sum().groupby(gens.carrier).sum()
    per_carrier_available = available.sum().groupby(gens.carrier).sum()
    return (per_carrier_curtailed / per_carrier_available * 100).fillna(0)


def electricity_buses(network):
    """Bus names for the electricity network only (excludes the H2 buses)."""
    return network.buses[network.buses.carrier == "AC"].index
