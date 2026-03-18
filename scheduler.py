"""
ILP Scheduler: Assign 19 staff to 24 concurrent jobs across 4 dates.
Objective: minimize max-min workload spread.
Reports external hire needs when internal staff is insufficient.
"""

try:
    import pulp
except ImportError:
    raise SystemExit("PuLP not found. Run: pip install pulp")

# ─── 1. DATA CONSTANTS ────────────────────────────────────────────────────────

PEOPLE = [
    "Ruizhe", "Yuxuan", "Wenqi", "Tongjia",
    "Yan", "Chenyue",
    "Shuyue",
    "Jingru",
    "Xingzhe", "Yuxinyue",
    "Yunbo", "Xinyang", "Wenyue", "Xiaorun", "Ruijia", "Kaiyang", "Dan",
    "Dongni", "Xingde",
]

# JOBS[j] = (date_label, time_slot, required_headcount)
JOBS = {
    1:  ("Mar 15", "1pm-3pm",   7),
    2:  ("Mar 15", "1pm-3pm",   4),
    3:  ("Mar 15", "1pm-3pm",   5),
    4:  ("Mar 15", "3:40pm-5:40pm", 4),
    5:  ("Mar 15", "3:40pm-5:40pm", 4),
    6:  ("Mar 15", "3:40pm-5:40pm", 6),
    7:  ("Apr 12", "1pm-3:30pm",    7),
    8:  ("Apr 12", "1pm-3:30pm",    4),
    9:  ("Apr 12", "1pm-3:30pm",    5),
    10: ("Apr 12", "3:40pm-5:40pm", 4),
    11: ("Apr 12", "3:40pm-5:40pm", 4),
    12: ("Apr 12", "3:40pm-5:40pm", 6),
    13: ("May 24", "1pm-3pm",   7),
    14: ("May 24", "1pm-3pm",   4),
    15: ("May 24", "1pm-3pm",   5),
    16: ("May 24", "3pm-5pm",   4),
    17: ("May 24", "3pm-5pm",   4),
    18: ("May 24", "3pm-5pm",   6),
    19: ("May 31", "1pm-3:30pm",7),
    20: ("May 31", "1pm-3:30pm",4),
    21: ("May 31", "1pm-3:30pm",5),
    22: ("May 31", "3:40pm-5:40pm", 4),
    23: ("May 31", "3:40pm-5:40pm", 4),
    24: ("May 31", "3:40pm-5:40pm", 6),
}

# Concurrent groups: within each group a person can take at most 1 job
CONCURRENT_GROUPS = {
    'A': [1, 2, 3],
    'B': [4, 5, 6],
    'C': [7, 8, 9],
    'D': [10, 11, 12],
    'E': [13, 14, 15],
    'F': [16, 17, 18],
    'G': [19, 20, 21],
    'H': [22, 23, 24],
}

# Cross-slot conflicts: none — all PM slots now start 3:40pm, after AM slots end (3pm/3:30pm).
# A person may work both AM and PM on the same date on all four dates.
CROSS_SLOT_CONFLICTS = []


def build_unavailability():
    """Return set of (person, job) pairs where the person cannot work."""
    unavail = set()
    mar15_all = list(range(1, 7))    # jobs 1-6
    mar15_am  = [1, 2, 3]            # jobs 1-3
    apr12_all = list(range(7, 13))   # jobs 7-12

    for p in ["Yan", "Dan", "Kaiyang", "Chenyue", "Tongjia"]:
        for j in mar15_all:
            unavail.add((p, j))

    for j in mar15_am:
        unavail.add(("Shuyue", j))

    for j in apr12_all:
        unavail.add(("Xiaorun", j))

    return unavail


# ─── 2. BUILD AND SOLVE ───────────────────────────────────────────────────────

def _make_base_model(job_ids, unavail):
    """Create base ILP model with variables and structural constraints (no objective)."""
    prob = pulp.LpProblem("Scheduler", pulp.LpMinimize)

    x = {(p, j): pulp.LpVariable(f"x_{p}_{j}", cat="Binary")
         for p in PEOPLE for j in job_ids}
    s = {j: pulp.LpVariable(f"s_{j}", lowBound=0, cat="Integer")
         for j in job_ids}
    W_max = pulp.LpVariable("W_max", lowBound=0, cat="Integer")
    W_min = pulp.LpVariable("W_min", lowBound=0, cat="Integer")

    # C1: Staffing — internal + external == required
    for j in job_ids:
        _, _, req = JOBS[j]
        prob += (pulp.lpSum(x[p, j] for p in PEOPLE) + s[j] == req,
                 f"staff_{j}")

    # C2: At most one job per concurrent group per person
    for grp, jobs in CONCURRENT_GROUPS.items():
        for p in PEOPLE:
            prob += (pulp.lpSum(x[p, j] for j in jobs) <= 1,
                     f"concurrent_{grp}_{p}")

    # C3: Cross-slot conflict — at most one job from the combined window
    for idx, jobs in enumerate(CROSS_SLOT_CONFLICTS):
        for p in PEOPLE:
            prob += (pulp.lpSum(x[p, j] for j in jobs) <= 1,
                     f"crossslot_{idx}_{p}")

    # C4: Availability — force zero for unavailable (person, job) pairs
    for (p, j) in unavail:
        prob += (x[p, j] == 0, f"unavail_{p}_{j}")

    # C5: W_max and W_min linearization
    for p in PEOPLE:
        workload = pulp.lpSum(x[p, j] for j in job_ids)
        prob += (W_max >= workload, f"wmax_{p}")
        prob += (W_min <= workload, f"wmin_{p}")

    return prob, x, s, W_max, W_min


def build_and_solve():
    unavail = build_unavailability()
    job_ids = list(JOBS.keys())
    solver = pulp.PULP_CBC_CMD(msg=0)

    # ── Phase 1: minimize total external hires ──────────────────────────────
    prob1, x1, s1, W_max1, W_min1 = _make_base_model(job_ids, unavail)
    prob1 += pulp.lpSum(s1[j] for j in job_ids)
    prob1.solve(solver)

    if pulp.LpStatus[prob1.status] not in ("Optimal", "Feasible"):
        raise RuntimeError(f"Phase 1 infeasible: {pulp.LpStatus[prob1.status]}")

    min_external = int(round(pulp.value(pulp.lpSum(s1[j] for j in job_ids))))

    # ── Phase 2: fix external total, minimize workload spread ───────────────
    prob2, x2, s2, W_max2, W_min2 = _make_base_model(job_ids, unavail)
    prob2 += (pulp.lpSum(s2[j] for j in job_ids) == min_external,
              "fix_external")
    prob2 += W_max2 - W_min2
    prob2.solve(solver)

    if pulp.LpStatus[prob2.status] not in ("Optimal", "Feasible"):
        raise RuntimeError(f"Phase 2 infeasible: {pulp.LpStatus[prob2.status]}")

    # Extract solution
    assign  = {j: [p for p in PEOPLE if pulp.value(x2[p, j]) > 0.5]
               for j in job_ids}
    extern  = {j: int(round(pulp.value(s2[j]))) for j in job_ids}
    workload = {p: sum(1 for j in job_ids if pulp.value(x2[p, j]) > 0.5)
                for p in PEOPLE}

    w_max_val = int(round(pulp.value(W_max2)))
    w_min_val = int(round(pulp.value(W_min2)))

    return assign, extern, workload, w_max_val, w_min_val


# ─── 3. OUTPUT FUNCTIONS ──────────────────────────────────────────────────────

def print_schedule(assign, extern):
    print("\n===== SCHEDULE =====")
    for j, (date, slot, req) in JOBS.items():
        internal = assign[j]
        ext = extern[j]
        n_int = len(internal)
        ext_str = f", [{ext} external]" if ext > 0 else ""
        names = ", ".join(internal) if internal else "(none)"
        print(f"Job {j:2d}  {date}  {slot:<12}  need {req}: "
              f"[{n_int} internal: {names}]{ext_str}")


def print_workload(workload, w_max, w_min):
    print("\n===== WORKLOAD SUMMARY =====")
    print(f"{'Person':<14} {'Assignments':>11}")
    print("-" * 28)
    for p in PEOPLE:
        print(f"{p:<14} {workload[p]:>11}")
    print("-" * 28)
    print(f"W_max={w_max}, W_min={w_min}, Spread={w_max - w_min}")


def print_external_needs(extern):
    print("\n===== EXTERNAL HIRE NEEDS =====")
    total = 0
    any_needed = False
    for j, (date, slot, req) in JOBS.items():
        if extern[j] > 0:
            print(f"Job {j:2d}  {date}  {slot:<12}  {extern[j]} external")
            total += extern[j]
            any_needed = True
    if not any_needed:
        print("No external hires needed.")
    else:
        print(f"\nTotal external needed: {total}")


# ─── 4. MAIN ──────────────────────────────────────────────────────────────────

def main():
    print("Solving ILP scheduling problem...")
    assign, extern, workload, w_max, w_min = build_and_solve()
    print("Solved.")

    print_schedule(assign, extern)
    print_workload(workload, w_max, w_min)
    print_external_needs(extern)


if __name__ == "__main__":
    main()
