from datetime import date

import pandas as pd
import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_dots as dots
from jobmarket import dashboard_profile as pr
from jobmarket import dashboard_progress as pg
from jobmarket import dashboard_theme as theme
from jobmarket import dashboard_ui as ui

TODAY = date.today()
WHERE = {  # a step's page -> the label and the colour of where it leads
    "views/practice.py": ("Практика", "grow"),
    "views/learn.py": ("Навчання", "grow"),
    "views/profile.py": ("Профіль", "grow"),
    "views/saved.py": ("Вакансії", "jobs"),
}

market = ui.table("fct_market_daily")
demand = ui.table("fct_skill_demand_monthly")
skills = ui.table("dim_skill")
update = ui.optional_document("last_update.json")
status = ui.optional_document("status.json")
vacancies = ui.catalog()

ui.header(
    "Ринок праці IT·UA",
    "вакансії DOU і Djinni · навички · стеки · зарплати · оновлюється щодня",
    eyebrow="dataward / головна",
    typed=True,
)

totals = dd.market_totals(market)
last = totals.iloc[-1]
month = dd.latest_month(demand)
ui.html(
    theme.stats(
        [
            ("Відкрито", dd.fmt_int(last["open_vacancies"])),
            ("Нових за день", dd.fmt_int(last["new_vacancies"])),
            ("Закрито за день", dd.fmt_int(last["closed_vacancies"])),
            ("Джерел", str(market["source"].nunique())),
        ],
        "market",
    )
)
if len(totals) < 2:
    ui.explain(
        "Це перший день спостереження: усі вакансії позначено «новими», бо раніше ми їх не бачили. "
        "Реальні нові й закриті з'являться з другого дня."
    )


# ---- today: what to do now, and where you stand ------------------------------------------------
def today() -> None:
    """What to do now and where you stand: about a person, so not on the public copy."""
    mine = ui.profile()
    ui.section("Сьогодні", domain="grow")
    state = ui.pet_state(mine, TODAY)
    ranked = pr.rank_vacancies(vacancies, mine) if vacancies is not None and mine.known() else None
    fit = pr.readiness(ranked) if ranked is not None else None
    plan = pr.learning_plan(ranked, mine.known(), top=1) if ranked is not None else None
    top = plan.iloc[0] if plan is not None and not plan.empty else None
    steps = pg.next_steps(
        mine,
        state["counts"],
        TODAY,
        top_skill=str(top["skill"]) if top is not None else None,
        unlocks=int(top["unlocks"]) if top is not None else 0,
    )
    left, right = st.columns([3, 2])
    with left:
        if steps:
            for step in steps[:3]:
                kind, domain = WHERE.get(step.page, ("Далі", "grow"))
                ui.html(theme.todo(kind, step.text, domain))
                st.page_link(step.page, label="Відкрити →")
        else:
            st.success("На сьогодні все: ціль виконано, повторювати нічого.")
    with right, ui.card("Ваш прогрес", "ціль дня і готовність до вакансій"):
        goal_ring, fit_ring = st.columns(2)
        done = min(state["today"] / max(mine.goal, 1), 1.0)
        with goal_ring:
            ui.html(
                dots.ring(done, "ціль дня", colour=theme.DOMAINS["grow"])
                + f'<div class="dw-ring-cap">ціль дня: {state["today"]}/{mine.goal}</div>'
            )
        with fit_ring:
            note = "готовність" if fit is not None else "додайте навички"
            ui.html(
                dots.ring(fit or 0.0, note, colour=theme.DOMAINS["jobs"])
                + f'<div class="dw-ring-cap">{note}</div>'
            )


if not ui.public_demo():
    today()

# ---- the breakdown panel: a metric split by source, level or direction -----------------------
ui.section("Ринок зараз", domain="market")


@st.fragment
def breakdown_panel() -> None:
    """Only this panel reruns when a selector changes."""
    with ui.card(
        "Вакансії по днях",
        ui.DAILY_NOTE,
    ):
        left, middle, right = st.columns([1, 2, 2])
        metric = middle.selectbox("Що рахувати", list(dd.METRICS), key="home_metric")
        split = right.selectbox("Ділити за", list(dd.BREAKDOWNS), key="home_split")
        daily, order = dd.daily_breakdown(market, dd.METRICS[metric], dd.BREAKDOWNS[split])
        names, colours = charts.series_domain(order, keep_order=True)
        left.markdown("")
        ui.html(theme.legend(names, colours))
        wide = daily.pivot_table(index="date", columns="series", values="value", fill_value=0)
        days = [f"{day:%d.%m}" for day in wide.index]
        parts = [
            (name, colour, wide[name].tolist() if name in wide else [0.0] * len(days))
            for name, colour in zip(names, colours, strict=True)
        ]
        ui.html(dots.columns(days, parts, unit=metric.lower()))


trend, shares = st.columns([3, 2])
with trend:
    breakdown_panel()
SPLITS = {"Джерела": "source", "Рівні": "seniority", "Напрямки": "category"}
with shares, ui.card("Структура ринку", "відкриті вакансії на останній день"):
    chosen = st.radio(
        "Розріз", list(SPLITS), horizontal=True, key="home_share", label_visibility="collapsed"
    )  # one chart at a time: tabs would draw all three on every rerun
    share = dd.latest_shares(market, SPLITS[chosen], top=4)
    share_names, share_colours = charts.series_domain(share["label"].tolist(), keep_order=True)
    share_parts = list(zip(share_names, share_colours, share["value"].tolist(), strict=True))
    ui.html(dots.waffle(share_parts) + dots.key(share_parts))
    ui.explain("100 крапок: кожна — один відсоток відкритих вакансій.")

# ---- directions: the way into the catalog ---------------------------------------------------
directions = dd.direction_stats(market, vacancies)
ui.section("Напрямки", domain="jobs")
target = "views/catalog.py" if vacancies is not None else "views/market.py"
filter_key = "cat_dirs" if vacancies is not None else "mk_cats"
for column, (n, row) in zip(
    st.columns(4), enumerate(directions.head(4).itertuples()), strict=False
):
    with column:
        ui.html(
            theme.direction_tile(
                n % 4, row.category, dd.fmt_int(row.open), row.share, list(row.skills)
            )
        )
        st.button(
            "Вакансії →" if vacancies is not None else "Розріз →",
            key=f"dir_{n}",
            on_click=ui.open_with,
            args=(target, filter_key, [row.category]),
            width="stretch",
        )

# ---- skills -------------------------------------------------------------------------------
ui.section("Навички", domain="market")
older = [m for m in dd.month_options(demand) if m < month]
ranking = dd.skill_ranking(demand, skills, ui.table("fct_salary_by_skill"), month=month,
                           previous=older[0] if older else None)  # fmt: skip
left, right = st.columns([3, 2])
with left, ui.card("Топ-10 навичок", f"частка вакансій місяця {month:%m.%Y}"):
    top = ranking.head(10).rename(columns={"canonical": "label", "share": "value"})
    ui.chart(charts.ranked_bars(top[["label", "value"]], fmt=".1%", unit="Частка вакансій"))
with right, ui.card("Що змінюється", "порівняння з минулим місяцем, в. п."):
    moved = ranking.dropna(subset=["change_pp"])
    if moved.empty:
        st.caption("Динаміка з'явиться, коли накопичиться другий місяць даних.")
    else:
        rising = moved.sort_values("change_pp", ascending=False).head(5)
        falling = moved.sort_values("change_pp").head(3)
        shown = pd.concat([rising, falling]).drop_duplicates("skill_id")
        st.dataframe(
            shown[["canonical", "change_pp"]].rename(
                columns={"canonical": "Навичка", "change_pp": "Зміна, п. п."}
            ),
            hide_index=True,
            column_config={"Зміна, п. п.": st.column_config.NumberColumn(format="%+.1f")},
        )

# ---- fresh vacancies (only where a catalog was built) --------------------------------------
if vacancies is not None:
    ui.section("Свіжі вакансії", domain="jobs")
    fresh = dd.sort_catalog(dd.filter_catalog(vacancies, only_open=True), "Нові спочатку").head(3)
    for column, (n, (_, row)) in zip(st.columns(3), enumerate(fresh.iterrows()), strict=False):
        with column:
            ui.html(
                theme.vacancy_tile(
                    n % 3,
                    str(row["title"]),
                    str(row["company"]),
                    dd.salary_label(row["salary_usd_min"], row["salary_usd_max"]),
                    list(row["skills"])[:4],
                )
            )
            st.link_button("Відкрити ↗", str(row["url"]), width="stretch")
    st.page_link("views/catalog.py", label="Весь каталог з фільтрами →")

# ---- the pipeline behind the numbers -----------------------------------------------------------
if status:
    ui.section("Конвеєр даних", domain="system")
    health = dd.health(status)
    runs = dd.run_states(status)
    marks = [theme.pulse(runs)] if runs else []
    marks.append(theme.pill(health[1], health[0]))
    if update:
        marks.append(theme.pill(f"дані: {dd.stamp(update['exported_at'])}"))
    ui.html(f'<div class="dw-pills">{"".join(marks)}</div>')
    checks = status.get("dq_latest", [])
    slos = status.get("slo", [])
    volumes = status.get("volumes", {})
    ui.html(
        theme.stats(
            [
                ("Перевірки DQ", f"{sum(c['status'] == 'pass' for c in checks)}/{len(checks)}"),
                ("SLO", f"{sum(s['ok'] is True for s in slos)}/{len(slos)}"),
                ("Вакансій у silver", dd.fmt_int(volumes.get("silver_vacancies", 0))),
                ("Спостережень", dd.fmt_int(volumes.get("silver_vacancy_sightings", 0))),
            ],
            "system",
        )
    )
    st.page_link("views/system.py", label="Запуски, перевірки якості й обсяги →")
