def solve_scenario(network, co2_limit=None, solver_name="highs", time_limit=3600, solver="ipm"):
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
    status, condition = network.optimize(
        solver_name=solver_name,
        solver_options={"time_limit": time_limit, "solver": solver},
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
