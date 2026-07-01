# DSEM-assignment-4-
Assignment four from data science for energy system modelling 

## How we work together

This repository is our shared workspace for Assignment 4.  
We use GitHub to store and organize the files, and Google Colab for most of the coding and notebook work.

### Folder structure

- `notebooks/` — all Colab notebooks.
- `src/` — reusable Python code and helper functions.
- `data_processed/` — processed data that the group can reuse.
- `results/` — figures, tables, and exported outputs.

### How to contribute

1. Create or switch to your own branch.
2. Open the notebook you want to work on in Google Colab.
3. Make your changes and test the code there.
4. Save the notebook back to your branch on GitHub.
5. When your part is ready, open a pull request so the group can review it.

### A few team rules

- Please do not push directly to `main`.
- Try to work in one notebook or one file at a time.
- Use clear file names and short commit messages.
- If you change a shared file, tell the group so nobody overwrites your work.
- Keep outputs that the team needs in `results/` or `data_processed/`.

### Working in Colab

To open a notebook:
- Go to Colab.
- Click **File → Open notebook**.
- Choose the **GitHub** tab.
- Select this repository and open the notebook you want.

To save your work:
- In Colab, click **File → Save a copy in GitHub**.
- Choose the correct repository and branch.
- Add a short commit message.
- Save it there so the rest of the group can see the update.

### Why we do it this way

This setup helps us work in parallel without losing each other’s changes.  
It also keeps the assignment organized, reproducible, and easy to review at the end.

## Data handling

The raw datasets are too large to store in GitHub.  
Each teammate should download the data once from the TU cloud link and keep it locally.

Processed files that are small enough to share are stored in `data_processed/`.  
If a file is missing, re-run the preprocessing notebook to regenerate it.