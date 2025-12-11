# Repo-specific Copilot instructions

This project is a small Streamlit-based CLI-config generator for Prisma Access remote-networks. Keep guidance focused and actionable for code edits and feature work.

-- **Entry points:** The UI/logic live in [config_gen11.py](../config_gen11.py) and [prismaa_bulk_rn_v1.py](../prismaa_bulk_rn_v1.py). Use `streamlit run <file>` to launch. Example:

  - `streamlit run config_gen11.py`

- **Primary libraries:** `streamlit`, `pandas`. Avoid adding heavy dependencies without justification.

- **Big picture:** This app generates CLI blocks using two main helpers:
  - `calculate_subnets(branch_str)` — deterministic subnet derivation from numeric branch IDs.
  - `generate_block(branch_num, region_display, subnets_str, psk, peer_ip="dynamic", spn_override=None)` — builds the full config text. Modify these functions to change generation logic.

- **Key constants to edit for environment changes:** top of the files: `TEMPLATE`, `TENANT`, `CRYPTO_IKE`, `CRYPTO_IPSEC`, `DOMAIN`.

- **Regions & SPNs:** The authoritative mapping is `REGION_MAP` (keys are the display names used in the UI). When adding regions, update this dict — `generate_block` expects the display-name to exist and will return an error string if not.

- **CSV bulk format:** The generated sample CSV (download button) uses columns: `Branch, Region, Peer IP, Subnets, PSK`. Bulk generation loops rows and calls `generate_block`. Keep that column order when adding tests or helpers.

- **Peer IP handling behaviour:**
  - `dynamic` or empty → IKE gateway uses `peer-address dynamic` and enables passive-mode.
  - explicit IP → `peer-address ip <ip>` and passive-mode is intentionally omitted.

- **Subnets behaviour:** Empty `Subnets` cell triggers `calculate_subnets`. The function strips digits from `Branch` and maps into three /24s. When changing auto-calculation, ensure bulk and single-site paths stay consistent.

- **UI state & keys to reference in code changes:** `st.session_state` keys used include `s_subnets`, `single_spn`, `branch_input`, `single_region_sel`. Respect these keys if you add or refactor UI components.

- **Error surface to watch for when running locally:** malformed CSV rows (missing Branch or Region) are skipped and logged to `error_log`; `generate_block` returns an error comment if a region isn't found. Streamlit runtime errors will show in the terminal that runs `streamlit run`.

- **When modifying generation output:** keep the output plain-text and bash-friendly (current code returns a large multi-line string). Tests or linters should validate that generated text contains expected markers like `set template` and the branch header comment `# BRANCH <num>`.

- **Where to add unit tests:** Add small tests that call `calculate_subnets()` and `generate_block()` directly (pure functions). Place tests at `tests/test_generation.py` and run with `pytest` after installing dev deps.

- **Non-goals / what not to change without discussion:** changing the overall UI paradigm (Streamlit → other framework) or introducing remote network/API calls. This repo is intentionally local/offline and generates CLI text for operator use.

If anything here is unclear or you want this file to include examples for a particular change (for example: adding a new Region, changing the subnet algorithm, or adding logging), tell me which part to expand and I will update it.
