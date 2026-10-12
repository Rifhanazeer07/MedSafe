import tkinter as tk
from tkinter import messagebox
import sqlite3
from contextlib import contextmanager

import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

DB_PATH = "MedicationSafety.db"
ROLES = ["Patient", "Admin"]
ROLE_DESCRIPTIONS = {
    "Patient": "Submit your own ADR reports and view your history.",
    "Admin": "Full access: manage users, view all data, run analysis.",
}

# Theme
DARK_BLUE = "#12355B"
BLUE = "#1976D2"
TEAL = "#00A6A6"
LIGHT_BLUE = "#EAF6FF"
WHITE = "#FFFFFF"
DARK_TEXT = "#17324D"
GREY = "#607D8B"
DANGER = "#C0392B"

current_username = None
current_role = None
login_window = None
username_entry = None
password_entry = None
login_role_var = None
role_hint_label = None


# =====================================================
# COMMON HELPERS
# =====================================================

def db_connect():
    return sqlite3.connect(DB_PATH)


def make_window(title, geometry):
    win = tk.Toplevel(login_window)
    win.title(title)
    win.geometry(geometry)
    win.configure(bg=LIGHT_BLUE)
    return win


def heading(parent, title, subtitle=None):
    tk.Label(parent, text=title, font=("Arial", 18, "bold"),
             bg=LIGHT_BLUE, fg=DARK_TEXT).pack(pady=(20, 3))
    if subtitle:
        tk.Label(parent, text=subtitle, font=("Arial", 11),
                 bg=LIGHT_BLUE, fg=GREY).pack(pady=(0, 15))


def button(parent, text, command, bg=TEAL, width=30):
    return tk.Button(parent, text=text, command=command,
                     font=("Arial", 11, "bold"), bg=bg, fg=WHITE,
                     activebackground=DARK_BLUE, activeforeground=WHITE,
                     width=width, height=2, bd=0, cursor="hand2")


def back_button(parent, window):
    button(parent, "← BACK TO DASHBOARD", window.destroy, GREY, 25).pack(pady=(5, 15))


@contextmanager
def connection():
    con = db_connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with connection() as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, username TEXT UNIQUE,
                password TEXT, role TEXT DEFAULT 'Patient'
            )
        """)
        cur.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cur.fetchall()]
        if "role" not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'Patient'")
        # Create the default Admin account
        cur.execute("SELECT 1 FROM users WHERE username = ?", ("admin",))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO users(name,email,username,password,role) VALUES(?,?,?,?,?)",
                ("Administrator", "admin@medsafe.com", "admin", "12345", "Admin")
            )

        cur.execute("""
            CREATE TABLE IF NOT EXISTS adr_records(
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT, age INTEGER, gender TEXT, department TEXT,
                drug TEXT, reaction TEXT, severity TEXT, serious TEXT,
                medication_error TEXT, outcome TEXT, date TEXT
            )
        """)


def get_data():
    with connection() as con:
        df = pd.read_sql("SELECT * FROM adr_records", con)
    for col in ["drug", "reaction", "department"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()
    return df


def check_data():
    df = get_data()
    if df.empty:
        messagebox.showwarning("No Data", "Please enter ADR records first.")
        return None
    return df


def count_yes(series):
    return series.astype(str).str.strip().str.lower().eq("yes").sum()


def stat_cards(parent, stats):
    frame = tk.Frame(parent, bg=LIGHT_BLUE)
    frame.pack(fill=tk.X, padx=20, pady=10)
    for title, value in stats:
        card = tk.Frame(frame, bg=WHITE, padx=20, pady=8, bd=1, relief=tk.SOLID)
        card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        tk.Label(card, text=title, font=("Arial", 10, "bold"),
                 bg=WHITE, fg=GREY).pack()
        tk.Label(card, text=str(value), font=("Arial", 18, "bold"),
                 bg=WHITE, fg=DARK_BLUE).pack(pady=4)


def show_2x2(window, plotter):
    fig = Figure(figsize=(12, 7), dpi=100, facecolor=LIGHT_BLUE)
    axes = [fig.add_subplot(221), fig.add_subplot(222),
            fig.add_subplot(223), fig.add_subplot(224)]
    plotter(*axes)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    canvas = FigureCanvasTkAgg(fig, master=window)
    canvas.draw()
    back_button(window, window)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)


# =====================================================
# LOGIN / LOGOUT
# =====================================================

def login():
    global current_username, current_role
    username = username_entry.get().strip()
    password = password_entry.get().strip()
    selected_role = login_role_var.get()

    with connection() as con:
        cur = con.cursor()
        cur.execute("SELECT username, role FROM users WHERE username=? AND password=?",
                    (username, password))
        user = cur.fetchone()

    if not user:
        messagebox.showerror("Error", "Invalid username or password")
        return
    if selected_role != user[1]:
        messagebox.showerror("Role Mismatch",
                             f"This account is registered as '{user[1]}'.\n"
                             f"Please select '{user[1]}' and try again.")
        return

    current_username, current_role = user
    messagebox.showinfo("Success", "Login successful!")
    login_window.withdraw()
    open_dashboard()


def logout():
    global current_username, current_role
    current_username = current_role = None
    for child in login_window.winfo_children():
        if isinstance(child, tk.Toplevel):
            child.destroy()
    username_entry.delete(0, tk.END)
    password_entry.delete(0, tk.END)
    login_role_var.set("Patient")
    login_window.deiconify()


def update_role_hint(*_):
    role_hint_label.config(text=ROLE_DESCRIPTIONS.get(login_role_var.get(), ""))


# =====================================================
# ADR ENTRY
# =====================================================

ADR_FIELDS = {
    "Patient ID": ("entry", None),
    "Age": ("entry", None),
    "Gender": ("option", ["Male", "Female", "Other"]),
    "Department": ("option", ["General Medicine", "Cardiology", "Neurology",
                                "Oncology", "Pediatrics", "ICU", "Emergency",
                                "Surgery", "Orthopedics", "Other"]),
    "Drug": ("entry", None),
    "Reaction": ("entry", None),
    "Severity": ("option", ["Mild", "Moderate", "Severe", "Life-threatening"]),
    "Serious": ("option", ["Yes", "No"]),
    "Medication Error": ("option", ["Yes", "No"]),
    "Outcome": ("option", ["Recovered", "Recovering", "Not Recovered",
                             "Hospitalized", "Fatal", "Unknown"]),
    "Date": ("entry", None),
}


def enter_adr_data():
    win = make_window("Enter ADR Data", "600x750")
    heading(win, "ADR DATA ENTRY", "Log a new adverse drug reaction record")

    form = tk.Frame(win, bg=WHITE, padx=20, pady=15, bd=1, relief=tk.SOLID)
    form.pack(pady=5, padx=30)
    widgets = {}

    for row, (label, (kind, options)) in enumerate(ADR_FIELDS.items()):
        tk.Label(form, text=label, bg=WHITE, fg=DARK_TEXT,
                 font=("Arial", 10, "bold")).grid(row=row, column=0,
                 padx=10, pady=7, sticky="w")
        if kind == "entry":
            w = tk.Entry(form, width=30, font=("Arial", 11))
        else:
            var = tk.StringVar()
            w = tk.OptionMenu(form, var, *options)
            w.config(width=26, bg=LIGHT_BLUE, fg=DARK_TEXT, highlightthickness=0)
            widgets[label] = var
            w.grid(row=row, column=1, padx=10, pady=7)
            continue
        w.grid(row=row, column=1, padx=10, pady=7)
        widgets[label] = w

    if current_role == "Patient":
        widgets["Patient ID"].insert(0, current_username)
        widgets["Patient ID"].config(state="disabled")

    def save():
        values = {k: v.get().strip() for k, v in widgets.items()}
        if any(not value for value in values.values()):
            messagebox.showerror("Error", "Please fill all fields.")
            return
        try:
            age = int(values["Age"])
            if not 0 < age <= 120:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid age.")
            return

        with connection() as con:
            con.execute("""
                INSERT INTO adr_records
                (patient_id, age, gender, department, drug, reaction, severity,
                 serious, medication_error, outcome, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (values["Patient ID"], age, values["Gender"], values["Department"],
                  values["Drug"], values["Reaction"], values["Severity"],
                  values["Serious"], values["Medication Error"], values["Outcome"],
                  values["Date"]))


        messagebox.showinfo("Success", "ADR record saved successfully!")
        for key, widget in widgets.items():
            if isinstance(widget, tk.Entry):
                widget.config(state="normal")
                widget.delete(0, tk.END)
                if current_role == "Patient" and key == "Patient ID":
                    widget.insert(0, current_username)
                    widget.config(state="disabled")
            else:
                widget.set("")

    button(win, "SAVE ADR RECORD", save, width=25).pack(pady=12)
    back_button(win, win)


# =====================================================
# VIEW RECORDS
# =====================================================

def view_records(own=False):
    df = get_data()
    if own and not df.empty:
        df = df[df["patient_id"].astype(str) == str(current_username)]

    title = "MY ADR RECORDS" if own else "ALL ADR RECORDS"
    subtitle = f"Records submitted under {current_username}" if own else "Admin view — every record in the system"
    win = make_window(title.title(), "1100x600")
    heading(win, title, subtitle)

    text = tk.Text(win, width=140, height=30, bg=WHITE, fg=DARK_TEXT,
                   font=("Consolas", 9), relief=tk.FLAT)
    text.pack(padx=15, pady=(0, 10), fill=tk.BOTH, expand=True)
    text.insert(tk.END, df.to_string(index=False) if not df.empty else
                ("You haven't submitted any ADR records yet." if own else "No ADR records found."))
    back_button(win, win)


def view_data():
    view_records(False)


def view_my_data():
    view_records(True)


# =====================================================
# ANALYSIS
# =====================================================

def hospital_analysis():
    df = check_data()
    if df is None:
        return
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    win = make_window("Hospital Analysis - Medication Safety", "1250x900")
    heading(win, "HOSPITAL MEDICATION SAFETY ANALYSIS", "Hospital ADR Monitoring Dashboard")
    stat_cards(win, [
        ("TOTAL ADR REPORTS", len(df)),
        ("AVERAGE PATIENT AGE", f"{df['age'].mean():.1f}"),
        ("SERIOUS ADRs", count_yes(df["serious"])),
        ("MEDICATION ERRORS", count_yes(df["medication_error"])),
    ])

    def plots(a1, a2, a3, a4):
        charts = [
            (a1, "department", "ADR Reports by Department", "bar"),
            (a2, "severity", "ADR Severity Distribution", "pie"),
            (a3, "medication_error", "Medication Error Reports", "bar"),
            (a4, "outcome", "Patient Outcomes", "pie"),
        ]
        for ax, col, title, kind in charts:
            s = df[col].value_counts()
            if kind == "pie":
                ax.pie(s.values, labels=s.index, autopct="%1.1f%%")
            else:
                ax.bar(s.index, s.values)
                ax.tick_params(axis="x", rotation=45)
                ax.set_ylabel("ADR Reports")
            ax.set_title(title)

    show_2x2(win, plots)


def pv_analysis():
    df = check_data()
    if df is None:
        return
    total = len(df)
    serious = count_yes(df["serious"])
    errors = count_yes(df["medication_error"])
    win = make_window("Pharmacovigilance Analysis", "1250x900")
    heading(win, "PHARMACOVIGILANCE ANALYSIS", "Adverse Drug Reaction Monitoring Dashboard")
    stat_cards(win, [
        ("TOTAL ADR REPORTS", total),
        ("SERIOUS ADRs", serious),
        ("SERIOUS ADR %", f"{serious / total * 100:.1f}%"),
        ("MEDICATION ERRORS", errors),
    ])

    def plots(a1, a2, a3, a4):
        for ax, col, title, kind in [
            (a1, "drug", "Top 10 Drugs by ADR Reports", "bar"),
            (a2, "reaction", "Top 10 Adverse Reactions", "bar"),
            (a3, "serious", "Serious vs Non-Serious ADRs", "pie"),
            (a4, "outcome", "ADR Outcomes", "bar"),
        ]:
            s = df[col].value_counts().head(10) if col in ["drug", "reaction"] else df[col].value_counts()
            if kind == "pie":
                ax.pie(s.values, labels=s.index, autopct="%1.1f%%")
            else:
                ax.bar(s.index, s.values)
                ax.tick_params(axis="x", rotation=45)
                ax.set_ylabel("Reports")
            ax.set_title(title)

    show_2x2(win, plots)


def show_all_graphs():
    df = check_data()
    if df is None:
        return
    win = make_window("Medication Safety Visualization", "1250x900")
    heading(win, "MEDICATION SAFETY VISUALIZATION")

    def plots(a1, a2, a3, a4):
        s = df["drug"].value_counts().head(10)
        a1.bar(s.index, s.values); a1.set_title("Top 10 Drugs by ADR Reports"); a1.tick_params(axis="x", rotation=45)
        s = df["severity"].value_counts()
        a2.pie(s.values, labels=s.index, autopct="%1.1f%%"); a2.set_title("ADR Severity")
        s = df["department"].value_counts()
        a3.bar(s.index, s.values); a3.set_title("Department-wise ADR Reports"); a3.tick_params(axis="x", rotation=45)
        s = df["serious"].value_counts()
        a4.pie(s.values, labels=s.index, autopct="%1.1f%%"); a4.set_title("Serious vs Non-Serious ADRs")

    show_2x2(win, plots)


# =====================================================
# DATASET GENERATION
# =====================================================

def generate_dataset():
    df = get_data()
    if df.empty:
        messagebox.showwarning("No Data", "Please enter ADR records first.")
        return

    df = df.drop_duplicates()
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["age"] = df["age"].fillna(df["age"].median())

    text_cols = ["gender", "department", "drug", "reaction", "severity",
                 "serious", "medication_error", "outcome"]
    for col in text_cols:
        df[col] = df[col].fillna("Unknown").astype(str).str.strip()

    df["Age Group"] = pd.cut(df["age"], [0, 18, 40, 60, 120],
                             labels=["0-18", "19-40", "41-60", "61+"])
    severity_score = {"Mild": 1, "Moderate": 2, "Severe": 3, "Life-Threatening": 4}
    df["Severity Score"] = df["severity"].map(severity_score).fillna(0)
    df["Serious ADR Flag"] = np.where(df["serious"].str.lower().eq("yes"), 1, 0)
    df["Medication Error Flag"] = np.where(df["medication_error"].str.lower().eq("yes"), 1, 0)

    def risk(row):
        if row["Serious ADR Flag"]:
            return "High Risk" if row["Severity Score"] >= 3 else "Moderate Risk"
        return "Moderate Risk" if row["Severity Score"] == 2 else "Low Risk"

    df["ADR Risk Category"] = df.apply(risk, axis=1)
    df["Report Date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["Report Month"] = df["Report Date"].dt.strftime("%Y-%m")

    output = "Medication_Safety_Dataset.csv"
    df.to_csv(output, index=False)
    messagebox.showinfo("Dataset Created",
                        f"Dataset created successfully!\n\n"
                        f"Total Records: {len(df)}\n"
                        f"Average Age: {df['age'].mean():.2f}\n"
                        f"Serious ADRs: {df['Serious ADR Flag'].sum()}\n"
                        f"Medication Errors: {df['Medication Error Flag'].sum()}\n\n"
                        f"Saved as:\n{output}")


# =====================================================
# USER MANAGEMENT
# =====================================================

def manage_users():
    win = make_window("Manage Users", "650x480")
    heading(win, "MANAGE USERS", "Admin — view and remove accounts")

    frame = tk.Frame(win, bg=LIGHT_BLUE)
    frame.pack(fill=tk.BOTH, expand=True, padx=20)
    scroll = tk.Scrollbar(frame)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    listbox = tk.Listbox(frame, font=("Consolas", 10), bg=WHITE, fg=DARK_TEXT,
                         yscrollcommand=scroll.set, selectbackground=TEAL,
                         selectforeground=WHITE)
    listbox.pack(fill=tk.BOTH, expand=True)
    scroll.config(command=listbox.yview)

    def refresh():
        listbox.delete(0, tk.END)
        with connection() as con:
            rows = con.execute("SELECT username,name,email,role FROM users ORDER BY username").fetchall()
        for username, name, email, role in rows:
            listbox.insert(tk.END, f"{username:<15} {name or '':<20} {email or '':<25} {role}")

    def delete_user():
        selected = listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a user to delete.")
            return
        username = listbox.get(selected[0]).split()[0]
        if username == current_username:
            messagebox.showerror("Error", "You can't delete your own account while logged in.")
            return
        if messagebox.askyesno("Confirm Delete", f"Delete user '{username}'? This can't be undone."):
            with connection() as con:
                con.execute("DELETE FROM users WHERE username=?", (username,))
            refresh()

    bar = tk.Frame(win, bg=LIGHT_BLUE)
    bar.pack(pady=12)
    button(bar, "DELETE SELECTED USER", delete_user, DANGER, 22).pack(side=tk.LEFT, padx=8)
    button(bar, "REFRESH", refresh, BLUE, 14).pack(side=tk.LEFT, padx=8)
    back_button(win, win)
    refresh()


# =====================================================
# DASHBOARD
# =====================================================

def open_dashboard():
    win = make_window("Smart Medication Safety & PV Analyzer", "700x700")
    win.protocol("WM_DELETE_WINDOW", login_window.destroy)

    tk.Label(win, text="SMART MEDICATION SAFETY & PV ANALYZER",
             font=("Arial", 18, "bold"), bg=LIGHT_BLUE, fg=DARK_TEXT).pack(pady=(25, 5))
    badge = DARK_BLUE if current_role == "Admin" else TEAL
    tk.Label(win, text=f"Logged in as {current_username}  •  {current_role.upper()}",
             font=("Arial", 10, "bold"), bg=badge, fg=WHITE,
             padx=14, pady=4).pack(pady=(0, 18))

    button(win, "ENTER ADR DATA", enter_adr_data).pack(pady=7)
    if current_role == "Admin":
        for text, command in [
            ("VIEW ADR DATA", view_data),
            ("HOSPITAL / ADR ANALYSIS", hospital_analysis),
            ("PHARMACOVIGILANCE ANALYSIS", pv_analysis),
            ("MATPLOTLIB VISUALIZATION", show_all_graphs),
            ("GENERATE DATASET", generate_dataset),
            ("MANAGE USERS", manage_users),
        ]:
            button(win, text, command, DARK_BLUE if text == "MANAGE USERS" else TEAL).pack(pady=7)
    else:
        button(win, "VIEW MY ADR DATA", view_my_data).pack(pady=7)

    button(win, "LOGOUT", logout, DANGER, 16).pack(pady=(10, 5))


# =====================================================
# REGISTER
# =====================================================

def register_window():
    win = make_window("MedSafe - Register", "500x900")
    tk.Label(win, text="💊", font=("Arial", 40), bg=LIGHT_BLUE).pack(pady=(20, 5))
    tk.Label(win, text="Create Account", font=("Arial", 25, "bold"),
             bg=LIGHT_BLUE, fg=DARK_TEXT).pack()
    tk.Label(win, text="Register for MedSafe", font=("Arial", 11),
             bg=LIGHT_BLUE, fg=GREY).pack(pady=(3, 10))

    form = tk.Frame(win, bg=WHITE, padx=35, pady=15)
    form.pack(padx=50, pady=(0, 15), fill=tk.X)
    fields = {}

    for label in ["Name", "Email", "Username", "Password", "Confirm Password"]:
        tk.Label(form, text=label, bg=WHITE, fg=DARK_TEXT,
                 font=("Arial", 10, "bold")).pack(anchor="w")
        entry = tk.Entry(form, width=30, font=("Arial", 12),
                         show="*" if "Password" in label else None)
        entry.pack(pady=(5, 10), ipady=5)
        fields[label] = entry

    tk.Label(form, text="Role", bg=WHITE, fg=DARK_TEXT,
             font=("Arial", 10, "bold")).pack(anchor="w")
    role_var = tk.StringVar(value="Patient")
    tk.OptionMenu(form, role_var, "Patient").pack(pady=(5, 5))
    hint = tk.Label(form, text=ROLE_DESCRIPTIONS["Patient"], bg=WHITE,
                    fg=GREY, font=("Arial", 9), wraplength=280, justify="left")
    hint.pack(pady=(0, 15))
    role_var.trace_add("write", lambda *_: hint.config(text=ROLE_DESCRIPTIONS.get(role_var.get(), "")))

    def create_account():
        values = {k: v.get().strip() for k, v in fields.items()}
        if any(not values[k] for k in ["Name", "Email", "Username", "Password"]):
            messagebox.showwarning("Missing Information", "Please fill all fields.")
            return
        if values["Password"] != values["Confirm Password"]:
            messagebox.showerror("Password Error", "Passwords do not match.")
            return
        try:
            with connection() as con:
                con.execute("INSERT INTO users(name,email,username,password,role) VALUES(?,?,?,?,?)",
                            (values["Name"], values["Email"], values["Username"],
                             values["Password"], "Patient"))
            messagebox.showinfo("Success", "Registration successful!\n\nYou can now login.")
            win.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists.")

    button(form, "CREATE ACCOUNT", create_account, width=25).pack()
    back_button(win, win)


# =====================================================
# APP START
# =====================================================

init_db()

login_window = tk.Tk()
login_window.title("MedSafe - Medication Safety & Pharmacovigilance")
login_window.geometry("900x680")
login_window.configure(bg=LIGHT_BLUE)

left = tk.Frame(login_window, bg=DARK_BLUE, width=400)
left.pack(side=tk.LEFT, fill=tk.BOTH)
left.pack_propagate(False)

tk.Label(left, text="💊", font=("Arial", 60), bg=DARK_BLUE, fg=WHITE).pack(pady=(80, 10))
tk.Label(left, text="MEDSAFE", font=("Arial", 30, "bold"), bg=DARK_BLUE, fg=WHITE).pack()
tk.Label(left, text="Medication Safety &\nPharmacovigilance", font=("Arial", 15),
         bg=DARK_BLUE, fg="#B9E8FF", justify="center").pack(pady=15)
tk.Label(left, text="Monitor  •  Analyze  •  Prevent", font=("Arial", 11),
         bg=DARK_BLUE, fg=WHITE).pack(pady=20)

right = tk.Frame(login_window, bg=WHITE)
right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

tk.Label(right, text="Welcome", font=("Arial", 30, "bold"), bg=WHITE, fg=DARK_TEXT).pack(pady=(70, 5))
tk.Label(right, text="Welcome to MedSafe", font=("Arial", 14), bg=WHITE, fg=GREY).pack()
tk.Label(right, text="Smart Medication Safety System", font=("Arial", 11), bg=WHITE, fg=GREY).pack(pady=10)

form = tk.Frame(right, bg=WHITE)
form.pack(pady=15)

tk.Label(form, text="Username", font=("Arial", 10, "bold"), bg=WHITE, fg=DARK_TEXT).pack(anchor="w")
username_entry = tk.Entry(form, width=32, font=("Arial", 12))
username_entry.pack(pady=(5, 12), ipady=6)

tk.Label(form, text="Password", font=("Arial", 10, "bold"), bg=WHITE, fg=DARK_TEXT).pack(anchor="w")
password_entry = tk.Entry(form, width=32, font=("Arial", 12), show="*")
password_entry.pack(pady=(5, 12), ipady=6)

tk.Label(form, text="Role", font=("Arial", 10, "bold"), bg=WHITE, fg=DARK_TEXT).pack(anchor="w")
login_role_var = tk.StringVar(value="Patient")
menu = tk.OptionMenu(form, login_role_var, *ROLES)
menu.config(width=27, bg=LIGHT_BLUE, fg=DARK_TEXT, highlightthickness=0)
menu.pack(pady=(5, 2))
role_hint_label = tk.Label(form, text=ROLE_DESCRIPTIONS["Patient"], font=("Arial", 9),
                           bg=WHITE, fg=GREY, wraplength=280, justify="left")
role_hint_label.pack(pady=(0, 15))
login_role_var.trace_add("write", update_role_hint)

button(form, "LOGIN", login, BLUE, 27).pack(pady=5)
tk.Label(right, text="Don't have an account?", font=("Arial", 10), bg=WHITE, fg=GREY).pack(pady=(12, 5))
button(right, "REGISTER", register_window, width=27).pack()
tk.Label(right, text="ADR Monitoring  |  Hospital Safety  |  PV Analysis",
         font=("Arial", 9), bg=WHITE, fg=GREY).pack(side=tk.BOTTOM, pady=25)

login_window.mainloop()
