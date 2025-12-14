import streamlit as st
import pandas as pd

# --- Vibe Coded by Toybox --- 

# --- Page Config ---
st.set_page_config(page_title="Prisma Access Config Generator", layout="wide")

st.title("🔌 Prisma Access Config Generator")
st.markdown("Generate CLI commands with **Backup Tunnel Support** and **Automated Descriptions**.")

# --- Constants & Data ---
st.sidebar.header("Global Configuration")
TEMPLATE = st.sidebar.text_input("Template Name", value="rn-tpl-fbm")
TENANT = st.sidebar.text_input("Tenant Name", value="fbm")
CRYPTO_IKE = st.sidebar.text_input("IKE Crypto Profile", value="velocloud-ike-crypto-primary")
CRYPTO_IPSEC = st.sidebar.text_input("IPSec Crypto Profile", value="velocloud-ipsec-crypto-default")
DOMAIN = st.sidebar.text_input("Domain", value="fbmsales.com")

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
    except ValueError:
        return "10.x.x.0/24"

# --- Helper: Config Builder for Peer IP ---
def get_peer_config_lines(ike_name, peer_ip):
    if not peer_ip or str(peer_ip).lower() == "dynamic":
        return f"""set template {TEMPLATE} config network ike gateway {ike_name} peer-address dynamic
set template {TEMPLATE} config network ike gateway {ike_name} protocol-common passive-mode yes"""
    else:
        return f"""set template {TEMPLATE} config network ike gateway {ike_name} peer-address ip {peer_ip}
# Note: Passive mode removed for static peer"""

# --- Helper: Generate Config Block ---
def generate_block(branch_num, region_display, subnets_str, psk_pri, peer_ip_pri="dynamic", 
                   enable_backup=False, psk_bak="", peer_ip_bak="dynamic", spn_override=None):
    
    if region_display not in REGION_MAP:
        return f"# ERROR: Region '{region_display}' not recognized"
    
    region_data = REGION_MAP[region_display]
    region_cli_id = region_data["id"]
    spn_name = spn_override if spn_override else region_data["spn"]

    branch_id = f"b{branch_num}"
    
    # Auto-calc subnets
    if not subnets_str or pd.isna(subnets_str):
        subnets_str = calculate_subnets(branch_num)

    # Clean Subnets
    cleaned_subnets = str(subnets_str).replace('"', '').replace("'", "").strip()
    if "," in cleaned_subnets:
        formatted_subnets = " ".join([s.strip() for s in cleaned_subnets.split(',')])
    else:
        formatted_subnets = cleaned_subnets

    # --- PRIMARY OBJECTS ---
    peer_id_pri = f"{branch_id}-primary.{DOMAIN}"
    ike_pri = f"{branch_id}-ikegw-pri"
    ipsec_pri = f"{branch_id}-ipsec-pri"
    
    # --- BACKUP OBJECTS ---
    peer_id_bak = f"{branch_id}-backup.{DOMAIN}"
    ike_bak = f"{branch_id}-ikegw-bak"
    ipsec_bak = f"{branch_id}-ipsec-bak"
    
    # Onboarding Object Name
    rn_name = f"{branch_id}-rn-{region_cli_id}" 

    # Comments
    ike_comment_pri = f"{branch_id} - IKE Gateway - {region_display} (Primary)"
    ipsec_comment_pri = f"{branch_id} - IPSec Tunnel - {region_display} (Primary)"
    ike_comment_bak = f"{branch_id} - IKE Gateway - {region_display} (Backup)"
    ipsec_comment_bak = f"{branch_id} - IPSec Tunnel - {region_display} (Backup)"

    # Get Peer Config Lines
    peer_config_pri = get_peer_config_lines(ike_pri, peer_ip_pri)
    
    # --- BUILD PRIMARY CONFIG ---
    config_str = f"""
# -------------------------------------------------------------------------
# BRANCH {branch_num} [{region_display}]
# -------------------------------------------------------------------------

# --- PRIMARY IKE GATEWAY ---
set template {TEMPLATE} config network ike gateway {ike_pri} protocol version ikev2
set template {TEMPLATE} config network ike gateway {ike_pri} protocol ikev2 dpd enable yes
set template {TEMPLATE} config network ike gateway {ike_pri} protocol ikev2 ike-crypto-profile {CRYPTO_IKE}
set template {TEMPLATE} config network ike gateway {ike_pri} local-address interface vlan
{peer_config_pri}
set template {TEMPLATE} config network ike gateway {ike_pri} protocol-common nat-traversal enable yes
set template {TEMPLATE} config network ike gateway {ike_pri} protocol-common fragmentation enable no
set template {TEMPLATE} config network ike gateway {ike_pri} peer-id type fqdn id {peer_id_pri}
set template {TEMPLATE} config network ike gateway {ike_pri} authentication pre-shared-key key {psk_pri}
set template {TEMPLATE} config network ike gateway {ike_pri} comment "{ike_comment_pri}"

# --- PRIMARY IPSEC TUNNEL ---
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} auto-key ike-gateway {ike_pri}
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} auto-key ipsec-crypto-profile {CRYPTO_IPSEC}
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} tunnel-monitor enable no
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} tunnel-interface tunnel
set template {TEMPLATE} config network tunnel ipsec {ipsec_pri} comment "{ipsec_comment_pri}"
"""

    # --- BUILD BACKUP CONFIG (Conditional) ---
    secondary_wan_cmd = "set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} secondary-wan-enabled no"
    secondary_tunnel_cmd = ""
    
    if enable_backup:
        peer_config_bak = get_peer_config_lines(ike_bak, peer_ip_bak)
        
        # Use Primary PSK if Backup PSK is empty
        final_psk_bak = psk_bak if psk_bak else psk_pri

        config_str += f"""
# --- BACKUP IKE GATEWAY ---
set template {TEMPLATE} config network ike gateway {ike_bak} protocol version ikev2
set template {TEMPLATE} config network ike gateway {ike_bak} protocol ikev2 dpd enable yes
set template {TEMPLATE} config network ike gateway {ike_bak} protocol ikev2 ike-crypto-profile {CRYPTO_IKE}
set template {TEMPLATE} config network ike gateway {ike_bak} local-address interface vlan
{peer_config_bak}
set template {TEMPLATE} config network ike gateway {ike_bak} protocol-common nat-traversal enable yes
set template {TEMPLATE} config network ike gateway {ike_bak} protocol-common fragmentation enable no
set template {TEMPLATE} config network ike gateway {ike_bak} peer-id type fqdn id {peer_id_bak}
set template {TEMPLATE} config network ike gateway {ike_bak} authentication pre-shared-key key {final_psk_bak}
set template {TEMPLATE} config network ike gateway {ike_bak} comment "{ike_comment_bak}"

# --- BACKUP IPSEC TUNNEL ---
set template {TEMPLATE} config network tunnel ipsec {ipsec_bak} auto-key ike-gateway {ike_bak}
set template {TEMPLATE} config network tunnel ipsec {ipsec_bak} auto-key ipsec-crypto-profile {CRYPTO_IPSEC}
set template {TEMPLATE} config network tunnel ipsec {ipsec_bak} tunnel-monitor enable no
set template {TEMPLATE} config network tunnel ipsec {ipsec_bak} tunnel-interface tunnel
set template {TEMPLATE} config network tunnel ipsec {ipsec_bak} comment "{ipsec_comment_bak}"
"""
        # Update Onboarding vars for backup
        secondary_wan_cmd = f"set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} secondary-wan-enabled yes"
        secondary_tunnel_cmd = f"set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} secondary-ipsec-tunnel {ipsec_bak}"

    # --- ONBOARDING CONFIG ---
    config_str += f"""
# --- ONBOARDING ---
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} protocol bgp enable no
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} region "{region_display}"
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} ipsec-tunnel {ipsec_pri}
{secondary_wan_cmd}
{secondary_tunnel_cmd}
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} subnets [ {formatted_subnets} ]
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} spn-name {spn_name}
set plugins cloud_services multi-tenant tenants {TENANT} remote-networks onboarding {rn_name} license-type FWAAS-AGGREGATE
"""

    return config_str

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
        
        st.markdown("---")
        st.subheader("Backup Settings")
        s_enable_backup = st.checkbox("Enable Backup Tunnel", value=False)
        
    with col2:
        s_peer_ip = st.text_input("Primary Peer IP", value="dynamic", help="Enter 'dynamic' or a static IP")
        s_subnets = st.text_area("Subnets (Auto-Calculated)", key="s_subnets")
        s_psk = st.text_input("Primary PSK", type="password", value="Secret123")
        
        if s_enable_backup:
            st.markdown("---")
            st.subheader(" ") # Spacer
            s_peer_ip_bak = st.text_input("Backup Peer IP", value="dynamic")
            s_psk_bak = st.text_input("Backup PSK", type="password", help="Leave empty to use Primary PSK")
        else:
            s_peer_ip_bak = "dynamic"
            s_psk_bak = ""

    if st.button("Generate Single Config"):
        res = generate_block(s_branch, s_region, s_subnets, s_psk, s_peer_ip, 
                             enable_backup=s_enable_backup, psk_bak=s_psk_bak, peer_ip_bak=s_peer_ip_bak, spn_override=s_spn)
        st.code(res, language="bash")

# ==========================================
# TAB 2: BULK UPLOAD
# ==========================================
with tab2:
    st.markdown("### Step 1: Download Template")
    st.info("💡 **Tip:** Set `Enable Backup` to `True` or `Yes` to generate a secondary tunnel.")
    
    # Sample data showing backup usage
    sample_data = [
        ["510", "US West", "dynamic", "", "Key1", "False", "", ""],
        ["613", "US East", "1.2.3.4", "", "Key2", "True", "5.6.7.8", "Key2Backup"],
        ["353", "US Central", "dynamic", "10.3.53.0/24", "Key3", "True", "dynamic", ""]
    ]
    df_sample = pd.DataFrame(sample_data, columns=["Branch", "Region", "Peer IP", "Subnets", "PSK", "Enable Backup", "Backup Peer IP", "Backup PSK"])
    csv_sample = df_sample.to_csv(index=False).encode('utf-8')

    st.download_button(
        label="📥 Download Sample CSV",
        data=csv_sample,
        file_name="prisma_bulk_template_v2.csv",
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
                    b_peer = "dynamic" if pd.isna(b_peer) or str(b_peer).strip() == "" else str(b_peer).strip()

                    # Subnet Handling
                    b_sub = row.get("Subnets", "")
                    b_sub = "" if pd.isna(b_sub) else str(b_sub).strip()

                    b_psk = str(row.get("PSK", "")).strip()
                    
                    # Backup Handling
                    raw_enable = str(row.get("Enable Backup", "False")).lower()
                    b_enable = raw_enable in ["true", "yes", "1", "on"]
                    
                    b_peer_bak = row.get("Backup Peer IP", "")
                    b_peer_bak = "dynamic" if pd.isna(b_peer_bak) or str(b_peer_bak).strip() == "" else str(b_peer_bak).strip()
                    
                    b_psk_bak = row.get("Backup PSK", "")
                    b_psk_bak = "" if pd.isna(b_psk_bak) else str(b_psk_bak).strip()

                    if not b_num or not b_reg:
                        error_log.append(f"Row {index+2}: Skipped (Missing Branch or Region)")
                        continue

                    block = generate_block(b_num, b_reg, b_sub, b_psk, b_peer, 
                                           enable_backup=b_enable, psk_bak=b_psk_bak, peer_ip_bak=b_peer_bak)
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