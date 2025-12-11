import streamlit as st
import pandas as pd

# --- Page Config ---
st.set_page_config(page_title="Prisma Access Config Generator", layout="wide")

st.title("🔌 Prisma Access Config Generator")
st.markdown("Generate CLI commands with **Peer IP Support** and **Automated Descriptions**.")

# --- Constants & Data ---
TEMPLATE = "rn-tpl-fbm"
TENANT = "fbm"
CRYPTO_IKE = "velocloud-ike-crypto-primary"
CRYPTO_IPSEC = "velocloud-ipsec-crypto-default"
DOMAIN = "fbmsales.com"

# REGION MAPPING
REGION_MAP = {
    "US Central":     {"id": "us-central",    "spn": "us-central-tanoak"},
    "US East":        {"id": "us-east",       "spn": "us-east-butternut"},
    "US Southeast":   {"id": "us-southeast",  "spn": "us-southeast-mahogony"},
    "US Northwest":   {"id": "us-northwest",  "spn": "us-northwest-scabiosa"},
    "US West":        {"id": "us-southwest",  "spn": "us-southwest-argan"},
    "US Northeast":   {"id": "us-east",       "spn": "us-east-butternut"},
    "US Southwest":   {"id": "us-southwest",  "spn": "us-southwest-argan"},
}

# --- Logic: Subnet Calculation ---
def calculate_subnets(branch_str):
    try:
        clean_num = ''.join(filter(str.isdigit, str(branch_str)))
        val = int(clean_num)
        octet3 = val % 100
        digit1 = val // 100
        s1 = f"10.{digit1}.{octet3}.0/24"
        s2 = f"10.{120 + digit1}.{octet3}.0/24"
        s3 = f"10.{130 + digit1}.{octet3}.0/24"
        return f"{s1}, {s2}, {s3}"
    except:
        return "10.x.x.0/24"

# --- Helper: Generate Config Block ---
def generate_block(branch_num, region_display, subnets_str, psk, peer_ip="dynamic", spn_override=None):
    if region_display not in REGION_MAP:
        return f"# ERROR: Region '{region_display}' not recognized"
    
    region_data = REGION_MAP[region_display]
    region_cli_id = region_data["id"]
    spn_name = spn_override if spn_override else region_data["spn"]

    branch_id = f"b{branch_num}"
    
    # Auto-calc subnets if empty
    if not subnets_str or pd.isna(subnets_str):
        subnets_str = calculate_subnets(branch_num)

    # Clean Subnets
    cleaned_subnets = str(subnets_str).replace('"', '').replace("'", "").strip()
    if "," in cleaned_subnets:
        formatted_subnets = " ".join([s.strip() for s in cleaned_subnets.split(',')])
    else:
        formatted_subnets = cleaned_subnets

    # Generate Object Names
    peer_id_pri = f"{branch_id}-primary.{DOMAIN}"
    ike_pri = f"{branch_id}-ikegw-pri"
    ipsec_pri = f"{branch_id}-ipsec-pri"
    rn_name = f"{branch_id}-rn-{region_cli_id}" 

    # Generate Automated Comments
    ike_comment = f"{branch_id} - IKE Gateway - {region_display}"
    ipsec_comment = f"{branch_id} - IPSec Tunnel - {region_display}"

    # Handle Peer IP Logic (Dynamic vs Static)
    if not peer_ip or peer_ip.lower() == "dynamic":
        peer_config = f"""set template {TEMPLATE} config network ike gateway {ike_pri} peer-address dynamic
set template {TEMPLATE} config network ike gateway {ike_pri} protocol-common passive-mode yes"""
    else:
        peer_config = f"""set template {TEMPLATE} config network ike gateway {ike_pri} peer-address ip {peer_ip}
# Note: Passive mode removed for static peer"""

    # Build Config String
    return f"""
# -------------------------------------------------------------------------
# BRANCH {branch_num} [{region_display}]
# -------------------------------------------------------------------------

# --- IKE GATEWAY ---
set template {TEMPLATE} config network ike gateway {ike_pri} protocol version ikev2
set template {TEMPLATE} config network ike gateway {ike_pri} protocol ikev2 dpd enable yes
set template {TEMPLATE} config network ike gateway {ike_pri} protocol ikev2 ike-crypto-profile {CRYPTO_IKE}
set template {TEMPLATE} config network ike gateway {ike_pri} local-address interface vlan
{peer_config}
set template {TEMPLATE} config network ike gateway {ike_pri} protocol-common nat-traversal enable yes
set template {TEMPLATE} config network ike gateway {ike_pri} protocol-common fragmentation enable no
set template {TEMPLATE} config network ike gateway {ike_pri} peer-id type fqdn id {peer_id_pri}
set template {TEMPLATE} config network ike gateway {ike_pri} authentication pre-shared-key key {psk}
set template {TEMPLATE} config network ike gateway {ike_pri} comment "{ike_comment}"

# --- IPSEC TUNNEL ---
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} auto-key ike-gateway {ike_pri}
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} auto-key ipsec-crypto-profile {CRYPTO_IPSEC}
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} tunnel-monitor enable no
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} tunnel-interface tunnel
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} comment "{ipsec_comment}"

# --- ONBOARDING ---
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} protocol bgp enable no
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} region "{region_display}"
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} ipsec-tunnel {ipsec_pri}
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} secondary-wan-enabled no
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} subnets [ {formatted_subnets} ]
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} spn-name {spn_name}
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} license-type FWAAS-AGGREGATE
"""

# --- Tabs ---
tab1, tab2 = st.tabs(["Single Site", "Bulk CSV Upload"])

# ==========================================
# TAB 1: SINGLE SITE
# ==========================================
with tab1:
    # Initialization
    if 's_subnets' not in st.session_state:
        st.session_state['s_subnets'] = calculate_subnets("351")
    if 'single_spn' not in st.session_state:
        st.session_state['single_spn'] = "us-central-tanoak"

    # Callbacks
    def update_single_subnets():
        b_num = st.session_state.branch_input
        st.session_state.s_subnets = calculate_subnets(b_num)

    def update_single_spn():
        sel = st.session_state.single_region_sel
        if sel in REGION_MAP:
            st.session_state.single_spn = REGION_MAP[sel]["spn"]

    col1, col2 = st.columns(2)
    with col1:
        s_branch = st.text_input("Branch Number", value="351", key="branch_input", on_change=update_single_subnets)
        s_region = st.selectbox("Region", options=list(REGION_MAP.keys()), key="single_region_sel", on_change=update_single_spn)
        s_spn = st.text_input("SPN Name", key="single_spn")
    with col2:
        s_peer_ip = st.text_input("Peer IP Address", value="dynamic", help="Enter 'dynamic' or a static IP (e.g., 1.2.3.4)")
        s_subnets = st.text_area("Subnets (Auto-Calculated)", key="s_subnets")
        s_psk = st.text_input("PSK", type="password", value="Secret123")
        
        # Display the Automated Comments for review
        st.caption(f"**Auto-Generated Comment:** b{s_branch} - [Type] - {s_region}")

    if st.button("Generate Single Config"):
        res = generate_block(s_branch, s_region, s_subnets, s_psk, s_peer_ip, s_spn)
        st.code(res, language="bash")

# ==========================================
# TAB 2: BULK UPLOAD
# ==========================================
with tab2:
    st.markdown("### Step 1: Download Template")
    st.info("💡 **Tip:** Leave `Subnets` empty to auto-calculate. Leave `Peer IP` empty to default to `dynamic`.")
    
    # Sample data showing dynamic default and static override
    sample_data = [
        ["510", "US West", "", "", "MySecretKey1"],
        ["613", "US East", "1.2.3.4", "", "MySecretKey2"],
        ["353", "US Central", "dynamic", "10.3.53.0/24", "MySecretKey3"]
    ]
    df_sample = pd.DataFrame(sample_data, columns=["Branch", "Region", "Peer IP", "Subnets", "PSK"])
    csv_sample = df_sample.to_csv(index=False).encode('utf-8')

    st.download_button(
        label="📥 Download Sample CSV",
        data=csv_sample,
        file_name="prisma_bulk_template.csv",
        mime="text/csv",
    )

    st.markdown("### Step 2: Upload CSV")
    uploaded_file = st.file_uploader("Upload your filled CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.success(f"Loaded {len(df)} branches.")
            
            if st.button("🚀 Generate Bulk Config"):
                full_config_output = ""
                error_log = []
                progress_bar = st.progress(0)

                for index, row in df.iterrows():
                    b_num = str(row.get("Branch", "")).strip()
                    b_reg = str(row.get("Region", "")).strip()
                    
                    # Peer IP Handling
                    b_peer = row.get("Peer IP", "")
                    if pd.isna(b_peer) or str(b_peer).strip() == "":
                        b_peer = "dynamic"
                    else:
                        b_peer = str(b_peer).strip()

                    # Subnet Handling
                    b_sub = row.get("Subnets", "")
                    if pd.isna(b_sub): b_sub = ""
                    else: b_sub = str(b_sub).strip()

                    b_psk = str(row.get("PSK", "")).strip()
                    
                    if not b_num or not b_reg:
                        error_log.append(f"Row {index+2}: Skipped (Missing Branch or Region)")
                        continue

                    block = generate_block(b_num, b_reg, b_sub, b_psk, b_peer)
                    full_config_output += block + "\n"
                    progress_bar.progress((index + 1) / len(df))

                if error_log:
                    st.error("Errors encountered:")
                    st.write(error_log)

                st.download_button(
                    label="💾 Download Full Config (.txt)",
                    data=full_config_output,
                    file_name="bulk_prisma_config.txt",
                    mime="text/plain"
                )
        except Exception as e:
            st.error(f"Error processing CSV: {e}")