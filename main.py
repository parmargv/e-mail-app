import streamlit as st
import imaplib
import email
import re
from email.header import decode_header

st.set_page_config(page_title="Mail Manager", page_icon="🗑️", layout="wide")
st.title("🗑️ Mail Manager")

# ── Provider config ────────────────────────────────────────────────────────────
PROVIDERS = {
    "Gmail": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "mailboxes": ["INBOX", "[Gmail]/Spam", "[Gmail]/Trash", "[Gmail]/All Mail"],
        "trash_folder": "[Gmail]/Trash",
        "help": (
            "Gmail requires an **App Password** (not your normal password).\n\n"
            "Enable at: Google Account → Security → 2-Step Verification → App passwords"
        ),
        "placeholder_email": "you@gmail.com",
        "placeholder_pass": "xxxx xxxx xxxx xxxx",
    },
    "Outlook / Hotmail": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "mailboxes": ["INBOX", "Junk", "Deleted"],
        "trash_folder": "Deleted",
        "help": (
            "Use your normal Microsoft account password.\n\n"
            "If you have 2FA enabled, generate an **App Password** at: "
            "account.microsoft.com → Security → Advanced security options → App passwords"
        ),
        "placeholder_email": "you@outlook.com / you@hotmail.com",
        "placeholder_pass": "your password or app password",
    },
    "Yahoo Mail": {
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "mailboxes": ["INBOX", "Bulk Mail", "Trash"],
        "trash_folder": "Trash",
        "help": (
            "Yahoo requires an **App Password**.\n\n"
            "Generate at: Account Security → App passwords"
        ),
        "placeholder_email": "you@yahoo.com",
        "placeholder_pass": "xxxx-xxxx-xxxx-xxxx",
    },
}

# ── Per-user session state initialisation ─────────────────────────────────────
_DEFAULTS = {
    "phase": "idle",
    "uid_queue": [],
    "total": 0,
    "deleted": 0,
    "failed": 0,
    "log": [],
    "permanent": False,
    "spam_results": [],
    "enable_move": False,
    "move_folder": "",
    "saved": 0,
    "mode": "",
    "senders": [],
    "provider_name": "Gmail",
    "user_email": "",
    "user_password": "",
    "mailbox": "INBOX",
    "delete_permanently": False,
    "enable_move_sidebar": False,
    "move_folder_sidebar": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📬 Email Provider")
    provider_name = st.selectbox(
        "Select your provider",
        list(PROVIDERS.keys()),
        index=list(PROVIDERS.keys()).index(st.session_state.provider_name),
        format_func=lambda x: {
            "Gmail": "📧 Gmail",
            "Outlook / Hotmail": "💼 Outlook / Hotmail",
            "Yahoo Mail": "🟣 Yahoo Mail",
        }[x],
        key="provider_name",
    )
    prov = PROVIDERS[provider_name]

    st.markdown("---")
    st.header("🔐 Login")
    st.info(prov["help"], icon="ℹ️")

    user_email = st.text_input(
        "Email Address",
        value=st.session_state.user_email,
        placeholder=prov["placeholder_email"],
        key="user_email",
    )
    user_password = st.text_input(
        "Password / App Password",
        value=st.session_state.user_password,
        type="password",
        placeholder=prov["placeholder_pass"],
        key="user_password",
    )

    st.markdown("---")
    mailbox = st.selectbox(
        "Mailbox",
        prov["mailboxes"],
        index=prov["mailboxes"].index(st.session_state.mailbox)
              if st.session_state.mailbox in prov["mailboxes"] else 0,
        key="mailbox",
    )
    delete_permanently = st.checkbox(
        "Permanently delete (skip Trash)",
        value=st.session_state.delete_permanently,
        key="delete_permanently",
    )

    st.markdown("---")
    st.header("📁 Move to Folder")
    enable_move = st.checkbox(
        "Move emails instead of deleting",
        value=st.session_state.enable_move_sidebar,
        key="enable_move_sidebar",
    )
    move_folder = ""
    if enable_move:
        move_folder = st.text_input(
            "Destination folder name",
            value=st.session_state.move_folder_sidebar,
            placeholder="e.g. Archives, Newsletters, [Gmail]/Work",
            help="The folder will be created automatically if it doesn't exist.",
            key="move_folder_sidebar",
        )
        st.caption("ℹ️ Emails will be **moved**, not deleted.")

    st.markdown("---")
    st.write("Design and Develop by Shri G.V.Parmar, A.V.P.T.I.Rajkot")
    st.markdown("---")
    with st.expander("📖 Setup Guide"):
        if provider_name == "Gmail":
            st.markdown("""
**Steps to get Gmail App Password:**
1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → Enable 2-Step Verification
3. Security → App passwords
4. Select app: Mail, device: Other → Generate
5. Copy the 16-char password here
            """)
        elif provider_name == "Outlook / Hotmail":
            st.markdown("""
**Steps for Outlook IMAP:**
1. Sign in at [account.microsoft.com](https://account.microsoft.com)
2. Go to Security → Advanced security options
3. If 2FA is on → App passwords → Create new
4. Use that password here

*Note: Make sure IMAP is enabled in Outlook Settings → Mail → Sync email*
            """)
        elif provider_name == "Yahoo Mail":
            st.markdown("""
**Steps to get Yahoo App Password:**
1. Sign in to Yahoo Account Security
2. Enable 2-Step Verification
3. Go to App passwords → Generate
4. Copy the password here
            """)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🎯 By Sender Address", "🛒 Commercial / Spam Filter", "🛡️ Smart Clean & Save"])

with tab1:
    st.subheader("Delete emails from specific addresses")
    sender_input = st.text_area(
        "One email address per line",
        placeholder="spam@example.com\nnewsletter@company.com\nalerts@somesite.com",
        height=130, key="sender_input",
    )
    c1, c2 = st.columns(2)
    preview_btn = c1.button("🔍 Preview", use_container_width=True, key="prev1")
    delete_btn  = c2.button("🗑️ Delete",  use_container_width=True, type="primary", key="del1")

with tab2:
    st.subheader("🛒 Auto-detect & delete commercial / marketing emails")
    st.markdown(
        "Scans your inbox and flags emails that look commercial using:\n"
        "- **List-Unsubscribe** header (legally required in bulk mail)\n"
        "- **Subject keywords**: sale, offer, deal, discount, % off, promo, newsletter, etc.\n"
        "- **Sender domain keywords**: noreply, newsletter, marketing, offers, promo, bulk, etc."
    )
    col_a, col_b = st.columns(2)
    with col_a:
        scan_limit  = st.number_input("Max emails to scan", min_value=50, max_value=5000, value=500, step=50)
        use_unsub   = st.checkbox("Flag emails with List-Unsubscribe header", value=True)
        use_subj    = st.checkbox("Flag by subject keywords", value=True)
    with col_b:
        use_domain  = st.checkbox("Flag by sender domain/name keywords", value=True)
        custom_keywords = st.text_input(
            "Extra subject keywords (comma-separated)",
            placeholder="voucher, cashback, exclusive",
        )
    c3, c4 = st.columns(2)
    spam_preview_btn = c3.button("🔍 Scan & Preview Commercial Emails", use_container_width=True, key="prev2")
    spam_delete_btn  = c4.button("🗑️ Delete All Found Commercial Emails", use_container_width=True, type="primary", key="del2")

with tab3:
    st.subheader("🛡️ Smart Clean & Save — Remove commercial emails, protect important ones")
    st.markdown(
        "Scans your inbox and does two things in one pass:\n\n"
        "- 💾 **Important senders** → always moved to your safe folder (whether commercial or not)\n"
        "- 🗑️ **Commercial / spam** from everyone else → deleted\n"
        "- 📭 Normal emails from other senders → left untouched"
    )

    st.markdown("#### 🔒 Step 1 — Important senders to protect")
    with st.expander("💡 What to enter here?", expanded=False):
        st.markdown("""
Enter **any part** of the sender's name or email address — the matching is flexible:

| What you type | Matches example |
|---|---|
| `ACPDC` | `ACPDC Newsletter <info@acpdc.in>` |
| `acpdc.in` | `noreply@acpdc.in` |
| `boss@company.com` | Exact email address |
| `@mybank.com` | Any email from that domain |

Use the **🔍 Preview** button first — the **From** column shows the exact text being matched against.
        """)
    t3_important_senders = st.text_area(
        "One sender email address per line (these will be saved, not deleted)",
        placeholder="boss@company.com\nbank@mybank.com\nschool@university.edu",
        height=120, key="t3_important_senders",
    )

    st.markdown("#### 📁 Step 2 — Safe folder for important emails")
    t3_safe_folder = st.text_input(
        "Folder name to move important emails into",
        placeholder="e.g. Important, SavedMail, [Gmail]/Important",
        key="t3_safe_folder",
        help="Created automatically if it doesn't exist.",
    )

    st.markdown("#### ⚙️ Step 3 — Commercial detection settings")
    col_t3a, col_t3b = st.columns(2)
    with col_t3a:
        t3_scan_limit = st.number_input("Max emails to scan", min_value=50, max_value=5000, value=500, step=50, key="t3_limit")
        t3_use_unsub  = st.checkbox("Flag emails with List-Unsubscribe header", value=True,  key="t3_unsub")
        t3_use_subj   = st.checkbox("Flag by subject keywords",                 value=True,  key="t3_subj")
    with col_t3b:
        t3_use_domain = st.checkbox("Flag by sender domain/name keywords",      value=True,  key="t3_domain")
        t3_custom_kw  = st.text_input("Extra subject keywords (comma-separated)",
                                      placeholder="voucher, cashback, exclusive", key="t3_custom_kw")

    st.markdown("---")
    col_p, col_r = st.columns(2)
    t3_preview_btn = col_p.button("🔍 Preview (show what will happen)", use_container_width=True, key="t3_prev")
    t3_run_btn     = col_r.button("🚀 Run Smart Clean", use_container_width=True, type="primary", key="t3_run")

# ── Keyword lists ──────────────────────────────────────────────────────────────
SUBJECT_SPAM_KEYWORDS = [
    "unsubscribe", "newsletter", "% off", "sale", "deal", "offer", "discount",
    "promo", "promotion", "coupon", "voucher", "cashback", "free shipping",
    "limited time", "act now", "don't miss", "exclusive", "special offer",
    "flash sale", "clearance", "buy now", "order now", "shop now",
    "win", "winner", "prize", "reward", "loyalty", "points",
]

DOMAIN_SPAM_KEYWORDS = [
    "noreply", "no-reply", "donotreply", "newsletter", "marketing",
    "offers", "promo", "promotions", "deals", "info@", "hello@",
    "news@", "updates@", "notifications@", "bulk", "mailer", "campaign",
    "email@", "mail@", "contact@", "nse_alerts@", "portfolio@portfolio",
    "ebill@airtel.com", "credit_cards@", "estatement@", "alerts@",
    "customercare@icicibank.com", "service@iciciprulife.com", "creditcards@",
]

# ── Core helpers ───────────────────────────────────────────────────────────────

def _get_session_creds():
    _prov = PROVIDERS[st.session_state.provider_name]
    return (
        _prov,
        st.session_state.user_email,
        st.session_state.user_password,
        st.session_state.mailbox,
    )

def connect_imap():
    _prov, _email, _password, _mailbox = _get_session_creds()
    imap = imaplib.IMAP4_SSL(_prov["imap_host"], _prov["imap_port"])
    imap.login(_email, _password)
    imap.select(f'"{_mailbox}"')
    return imap

def decode_str(value):
    parts = decode_header(value or "")
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(part))
    return " ".join(out)

def is_commercial(msg, use_unsub, use_subj, use_domain, extra_kw):
    if use_unsub and msg.get("List-Unsubscribe"):
        return True, "Has List-Unsubscribe header"
    subject = decode_str(msg.get("Subject", "")).lower()
    sender  = decode_str(msg.get("From",    "")).lower()
    if use_subj:
        all_kw = SUBJECT_SPAM_KEYWORDS + [k.strip().lower() for k in extra_kw.split(",") if k.strip()]
        for kw in all_kw:
            if kw in subject:
                return True, f"Subject contains '{kw}'"
    if use_domain:
        for kw in DOMAIN_SPAM_KEYWORDS:
            if kw in sender:
                return True, f"Sender contains '{kw}'"
    return False, ""

def search_all_uids(senders):
    imap = connect_imap()
    uid_list = []
    for sender in senders:
        status, data = imap.uid("search", None, f'FROM "{sender}"')
        if status == "OK" and data[0]:
            for uid in data[0].split():
                uid_list.append((sender, uid))
    imap.logout()
    return uid_list

def fetch_preview(senders):
    imap = connect_imap()
    rows = []
    for sender in senders:
        status, data = imap.uid("search", None, f'FROM "{sender}"')
        if status == "OK" and data[0]:
            for uid in data[0].split():
                s, d = imap.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE FROM)])")
                if s == "OK":
                    msg = email.message_from_bytes(d[0][1])
                    rows.append({
                        "from":    decode_str(msg.get("From",    "")),
                        "subject": decode_str(msg.get("Subject", "(no subject)")),
                        "date":    msg.get("Date", ""),
                    })
    imap.logout()
    return rows

def scan_commercial(limit, use_unsub, use_subj, use_domain, extra_kw):
    imap = connect_imap()
    status, data = imap.uid("search", None, "ALL")
    if status != "OK" or not data[0]:
        imap.logout()
        return []
    all_uids = data[0].split()
    recent   = all_uids[-limit:]
    results  = []
    for uid in recent:
        s, d = imap.uid("fetch", uid, "(BODY.PEEK[HEADER])")
        if s != "OK":
            continue
        msg = email.message_from_bytes(d[0][1])
        flagged, reason = is_commercial(msg, use_unsub, use_subj, use_domain, extra_kw)
        if flagged:
            results.append({
                "uid":     uid.decode(),
                "from":    decode_str(msg.get("From",    "")),
                "subject": decode_str(msg.get("Subject", "(no subject)")),
                "date":    msg.get("Date", ""),
                "reason":  reason,
            })
    imap.logout()
    return results

def sender_matches_important(sender_raw, important_lower):
    raw = sender_raw.lower()
    email_match = re.search(r'<([^>]+)>', raw)
    email_addr  = email_match.group(1) if email_match else raw
    for imp in important_lower:
        imp = imp.strip().strip('<>').strip()
        if not imp:
            continue
        if imp in raw:
            return True
        if imp in email_addr:
            return True
    return False

def scan_smart_clean(limit, use_unsub, use_subj, use_domain, extra_kw, important_senders):
    imap = connect_imap()
    status, data = imap.uid("search", None, "ALL")
    if status != "OK" or not data[0]:
        imap.logout()
        return []
    all_uids = data[0].split()
    recent   = all_uids[-limit:]
    results  = []
    important_lower = [s.strip().lower() for s in important_senders if s.strip()]
    for uid in recent:
        s, d = imap.uid("fetch", uid, "(BODY.PEEK[HEADER])")
        if s != "OK":
            continue
        msg        = email.message_from_bytes(d[0][1])
        sender_raw = decode_str(msg.get("From", ""))
        is_important = sender_matches_important(sender_raw, important_lower)

        if is_important:
            results.append({
                "uid":     uid.decode(),
                "from":    sender_raw,
                "subject": decode_str(msg.get("Subject", "(no subject)")),
                "date":    msg.get("Date", ""),
                "reason":  "✅ Important sender",
                "action":  "💾 Save",
            })
        else:
            flagged, reason = is_commercial(msg, use_unsub, use_subj, use_domain, extra_kw)
            if flagged:
                results.append({
                    "uid":     uid.decode(),
                    "from":    sender_raw,
                    "subject": decode_str(msg.get("Subject", "(no subject)")),
                    "date":    msg.get("Date", ""),
                    "reason":  reason,
                    "action":  "🗑️ Delete",
                })
    imap.logout()
    return results

def delete_one(uid_str, permanent):
    _prov, _, _, _ = _get_session_creds()
    imap  = connect_imap()
    uid   = uid_str.encode() if isinstance(uid_str, str) else uid_str
    trash = _prov["trash_folder"]
    if permanent:
        imap.uid("store", uid, "+FLAGS", "\\Deleted")
        imap.expunge()
    else:
        imap.uid("copy",  uid, trash)
        imap.uid("store", uid, "+FLAGS", "\\Deleted")
        imap.expunge()
    imap.logout()

def ensure_folder(imap, folder):
    status, _ = imap.select(f'"{folder}"')
    if status != "OK":
        imap.create(f'"{folder}"')
    imap.select(f'"{st.session_state.mailbox}"')

def move_one(uid_str, destination):
    imap = connect_imap()
    uid  = uid_str.encode() if isinstance(uid_str, str) else uid_str
    ensure_folder(imap, destination)
    imap.uid("copy",  uid, f'"{destination}"')
    imap.uid("store", uid, "+FLAGS", "\\Deleted")
    imap.expunge()
    imap.logout()

# ── Validation helpers ─────────────────────────────────────────────────────────

def validate_creds():
    if not st.session_state.user_email or not st.session_state.user_password:
        st.error("Enter your email credentials in the sidebar.")
        return False
    return True

def validate_senders():
    senders = [s.strip() for s in st.session_state.sender_input.strip().splitlines() if s.strip()]
    if not senders:
        st.error("Enter at least one sender address.")
        return None
    return senders

# ── Tab 1 actions ──────────────────────────────────────────────────────────────
if preview_btn:
    if validate_creds():
        senders = validate_senders()
        if senders:
            with st.spinner("Fetching emails..."):
                try:
                    rows = fetch_preview(senders)
                except Exception as e:
                    st.error(f"Connection error: {e}")
                    st.stop()
            if rows:
                st.success(f"Found **{len(rows)}** email(s).")
                st.dataframe(rows, width="stretch", hide_index=True)
            else:
                st.info("No emails found from those senders.")

if delete_btn:
    if validate_creds():
        senders = validate_senders()
        if senders:
            if enable_move and not move_folder.strip():
                st.error("Please enter a destination folder name.")
            else:
                st.session_state.phase       = "scanning"
                st.session_state.mode        = "sender"
                st.session_state.permanent   = delete_permanently
                st.session_state.enable_move = enable_move
                st.session_state.move_folder = move_folder.strip()
                st.session_state.senders     = senders
                st.rerun()

# ── Tab 2 actions ──────────────────────────────────────────────────────────────
if spam_preview_btn:
    if validate_creds():
        with st.spinner(f"Scanning last {scan_limit} emails for commercial content..."):
            try:
                results = scan_commercial(scan_limit, use_unsub, use_subj, use_domain, custom_keywords)
                st.session_state.spam_results = results
            except Exception as e:
                st.error(f"Connection error: {e}")
                st.stop()
        if results:
            st.success(f"Found **{len(results)}** commercial email(s).")
            st.dataframe(results, width="stretch", hide_index=True)
        else:
            st.info("No commercial emails detected with current settings.")

if spam_delete_btn:
    if validate_creds():
        if enable_move and not move_folder.strip():
            st.error("Please enter a destination folder name.")
        else:
            with st.spinner(f"Scanning last {scan_limit} emails..."):
                try:
                    results = scan_commercial(scan_limit, use_unsub, use_subj, use_domain, custom_keywords)
                except Exception as e:
                    st.error(f"Connection error: {e}")
                    st.stop()
            if not results:
                st.info("No commercial emails found.")
            else:
                st.session_state.phase       = "deleting"
                st.session_state.mode        = "spam"
                st.session_state.permanent   = delete_permanently
                st.session_state.enable_move = enable_move
                st.session_state.move_folder = move_folder.strip()
                st.session_state.uid_queue   = [("commercial", r["uid"]) for r in results]
                st.session_state.total       = len(results)
                st.session_state.deleted     = 0
                st.session_state.failed      = 0
                st.session_state.log         = []
                st.rerun()

# ── Tab 3 actions ──────────────────────────────────────────────────────────────
def _t3_validate():
    if not validate_creds():
        return False
    if not t3_safe_folder.strip():
        st.error("Please enter a safe folder name in Step 2.")
        return False
    return True

if t3_preview_btn:
    if _t3_validate():
        important = [s.strip() for s in t3_important_senders.strip().splitlines() if s.strip()]
        with st.spinner(f"Scanning last {t3_scan_limit} emails..."):
            try:
                results = scan_smart_clean(t3_scan_limit, t3_use_unsub, t3_use_subj,
                                           t3_use_domain, t3_custom_kw, important)
            except Exception as e:
                st.error(f"Connection error: {e}")
                st.stop()
        if results:
            save_count   = sum(1 for r in results if "Save" in r["action"])
            delete_count = len(results) - save_count
            st.success(
                f"Found **{len(results)}** commercial email(s) — "
                f"💾 **{save_count}** will be saved to `{t3_safe_folder}`, "
                f"🗑️ **{delete_count}** will be deleted."
            )
            st.dataframe(results, width="stretch", hide_index=True)

            with st.expander("🔬 Debug — exact 'From' values (copy to use as important sender)", expanded=save_count == 0):
                st.caption("These are the exact decoded From fields. Copy any part (name or email address) into Step 1.")
                unique_froms = sorted({r["from"] for r in results})
                for f in unique_froms:
                    st.code(f, language=None)
        else:
            st.info("No commercial emails found with current settings.")

if t3_run_btn:
    if _t3_validate():
        important = [s.strip() for s in t3_important_senders.strip().splitlines() if s.strip()]
        with st.spinner(f"Scanning last {t3_scan_limit} emails..."):
            try:
                results = scan_smart_clean(t3_scan_limit, t3_use_unsub, t3_use_subj,
                                           t3_use_domain, t3_custom_kw, important)
            except Exception as e:
                st.error(f"Connection error: {e}")
                st.stop()
        if not results:
            st.info("No commercial emails found.")
        else:
            st.session_state.phase       = "deleting"
            st.session_state.mode        = "smart"
            st.session_state.permanent   = delete_permanently
            st.session_state.enable_move = False
            st.session_state.move_folder = t3_safe_folder.strip()
            st.session_state.uid_queue   = [(r["action"], r["uid"]) for r in results]
            st.session_state.total       = len(results)
            st.session_state.deleted     = 0
            st.session_state.saved       = 0
            st.session_state.failed      = 0
            st.session_state.log         = []
            st.rerun()

# ── Scanning phase ─────────────────────────────────────────────────────────────
if st.session_state.phase == "scanning" and st.session_state.get("mode") == "sender":
    st.info("📡 Scanning mailbox...")
    with st.spinner("Searching..."):
        try:
            uid_queue = search_all_uids(st.session_state.senders)
        except Exception as e:
            st.error(f"Scan failed: {e}")
            st.session_state.phase = "idle"
            st.stop()
    if not uid_queue:
        st.warning("No emails found.")
        st.session_state.phase = "idle"
    else:
        st.session_state.uid_queue = [(s, u.decode() if isinstance(u, bytes) else u) for s, u in uid_queue]
        st.session_state.total   = len(uid_queue)
        st.session_state.deleted = 0
        st.session_state.failed  = 0
        st.session_state.log     = []
        st.session_state.phase   = "deleting"
        st.rerun()

# ── Deleting phase ─────────────────────────────────────────────────────────────
if st.session_state.phase == "deleting":
    total   = st.session_state.total
    deleted = st.session_state.deleted
    failed  = st.session_state.failed
    done    = deleted + failed
    queue   = st.session_state.uid_queue
    pct     = done / total if total > 0 else 0

    is_smart = st.session_state.get("mode") == "smart"
    st.markdown("### ⚙️ Processing emails...")
    st.progress(pct, text=f"Progress: {done}/{total}  ({int(pct*100)}%)")

    if is_smart:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🗑️ Deleted",   deleted)
        c2.metric("💾 Saved",     st.session_state.get("saved", 0))
        c3.metric("❌ Failed",    failed)
        c4.metric("⏳ Remaining", total - done)
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Deleted",   deleted)
        c2.metric("❌ Failed",    failed)
        c3.metric("⏳ Remaining", total - done)

    if st.session_state.log:
        with st.expander("📋 Live Log", expanded=True):
            for line in st.session_state.log[-40:]:
                st.markdown(line)

    if queue:
        label, uid_str = queue[0]
        st.session_state.uid_queue = queue[1:]
        try:
            if is_smart:
                if "Save" in label:
                    move_one(uid_str, st.session_state.move_folder)
                    st.session_state.saved   = st.session_state.get("saved", 0) + 1
                    st.session_state.deleted += 1
                    action_word = f"💾 Saved → `{st.session_state.move_folder}`"
                else:
                    delete_one(uid_str, st.session_state.permanent)
                    st.session_state.deleted += 1
                    action_word = "🗑️ Deleted"
            elif st.session_state.enable_move and st.session_state.move_folder:
                move_one(uid_str, st.session_state.move_folder)
                st.session_state.deleted += 1
                action_word = f"📁 Moved to **{st.session_state.move_folder}**"
            else:
                delete_one(uid_str, st.session_state.permanent)
                st.session_state.deleted += 1
                action_word = "🗑️ Deleted"
            st.session_state.log.append(
                f"✅ `{uid_str}` from **{label}** — {action_word} ({st.session_state.deleted}/{total})"
            )
        except Exception as ex:
            st.session_state.failed += 1
            st.session_state.log.append(f"❌ Failed `{uid_str}`: {ex}")
        st.rerun()
    else:
        st.session_state.phase = "done"
        st.rerun()

# ── Done ───────────────────────────────────────────────────────────────────────
if st.session_state.phase == "done":
    is_smart_done = st.session_state.get("mode") == "smart"
    st.markdown("### 🏁 Complete!")

    if is_smart_done:
        saved_count = st.session_state.get("saved", 0)
        del_count   = st.session_state.deleted - saved_count
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🗑️ Deleted",        del_count)
        c2.metric("💾 Saved",           saved_count)
        c3.metric("❌ Failed",          st.session_state.failed)
        c4.metric("📋 Total processed", st.session_state.total)
        if st.session_state.failed == 0:
            st.success(
                f"🎉 Done! **{del_count}** email(s) deleted, "
                f"**{saved_count}** important email(s) saved to `{st.session_state.move_folder}`."
            )
        else:
            st.warning(
                f"Done — **{del_count}** deleted, **{saved_count}** saved, "
                f"**{st.session_state.failed}** failed."
            )
    else:
        action_label = (
            f"moved to **{st.session_state.move_folder}**"
            if st.session_state.enable_move and st.session_state.move_folder
            else "removed"
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Processed",       st.session_state.deleted)
        c2.metric("❌ Failed",          st.session_state.failed)
        c3.metric("📋 Total processed", st.session_state.total)
        if st.session_state.failed == 0:
            st.success(f"🎉 All **{st.session_state.deleted}** email(s) {action_label} successfully!")
        else:
            st.warning(f"Done — **{st.session_state.deleted}** {action_label}, **{st.session_state.failed}** failed.")

    with st.expander("📋 Full Log"):
        for line in st.session_state.log:
            st.markdown(line)

    if st.button("🔄 Start over"):
        st.session_state.phase = "idle"
        st.rerun()

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
imap_info = {
    "Gmail":             "imap.gmail.com:993",
    "Outlook / Hotmail": "outlook.office365.com:993",
    "Yahoo Mail":        "imap.mail.yahoo.com:993",
}
st.caption(f"Connected via {imap_info[provider_name]}. Credentials are never stored.")