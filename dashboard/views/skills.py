import streamlit as st

from jobmarket import dashboard_charts as charts
from jobmarket import dashboard_data as dd
from jobmarket import dashboard_ui as ui

ui.header(
    "Навички",
    "Чого вимагають вакансії: рейтинг навичок, докладно про одну з них і стеки, "
    "які майже завжди йдуть разом.",
    eyebrow="Аналітика · навички",
    domain="market",
)

skills = ui.table("dim_skill")
demand = ui.table("fct_skill_demand_monthly")
pairs = ui.table("fct_skill_pairs")
salary = ui.table("fct_salary_by_skill")
clusters = ui.table("skill_clusters")

ranking_tab, skill_tab, stacks_tab = st.tabs(["Рейтинг", "Навичка", "Стеки"])

# ---- the ranking: a list to search, sort and take away ---------------------------------------
with ranking_tab:
    months = dd.month_options(demand)
    one, two, three = st.columns([2, 2, 1])
    query = one.text_input("Пошук навички", placeholder="наприклад, python", key="rank_query")
    groups = two.multiselect(
        "Група", sorted(skills["category"].dropna().unique()), key="rank_groups"
    )
    month = three.selectbox("Місяць", months, format_func=lambda m: f"{m:%m.%Y}", key="rank_month")
    older = [m for m in months if m < month]
    ranking = dd.skill_ranking(
        demand, skills, salary, month=month, previous=older[0] if older else None
    )
    if query:
        ranking = ranking[ranking["canonical"].str.contains(query.strip(), case=False, regex=False)]
    if groups:
        ranking = ranking[ranking["category"].isin(groups)]

    if ranking.empty:
        st.info("За цими умовами навичок немає.")
    else:
        top = ranking.head(15)
        with ui.card(
            f"Топ-{len(top)} за часткою вакансій",
            f"місяць {month:%m.%Y}; у відсотках від усіх унікальних вакансій місяця.",
        ):
            ui.chart(
                charts.ranked_bars(
                    top.rename(columns={"canonical": "label", "share": "value"})[
                        ["label", "value"]
                    ],
                    fmt=".1%",
                    unit="Частка вакансій",
                )  # fmt: skip
            )
        table = ranking.assign(
            **{
                "№": range(1, len(ranking) + 1),
                "Частка вакансій, %": (ranking["share"] * 100).round(1),
                "Обов'язкова, %": (ranking["required_share"] * 100).round(1),
            }
        ).rename(
            columns={
                "canonical": "Навичка", "category": "Група", "vacancies": "Вакансій",
                "change_pp": "Зміна, п. п.", "salary_median": "Медіана вилки, USD",
            }
        )  # fmt: skip
        st.caption(
            f"{len(table)} навичок. Клік по заголовку сортує. «Обов'язкова» — у скількох вакансіях "
            "навичку названо вимогою, а не бажаною. «Зміна» — проти попереднього місяця. "
            "Зарплата — лише з вакансій, де її вказано (вибірка зміщена)."
        )
        st.dataframe(
            table[
                [
                    "№",
                    "Навичка",
                    "Група",
                    "Вакансій",
                    "Частка вакансій, %",
                    "Обов'язкова, %",
                    "Зміна, п. п.",
                    "Медіана вилки, USD",
                ]
            ],  # fmt: skip
            hide_index=True,
            height=460,
            column_config={
                "Частка вакансій, %": st.column_config.ProgressColumn(
                    format="%.1f", min_value=0, max_value=float(table["Частка вакансій, %"].max())
                ),
                "Зміна, п. п.": st.column_config.NumberColumn(format="%+.1f"),
                "Медіана вилки, USD": st.column_config.NumberColumn(format="%d"),
            },
        )
        st.download_button(
            "Завантажити CSV",
            table.drop(columns=["skill_id", "share", "required_share"])
            .to_csv(index=False)
            .encode("utf-8"),
            file_name=f"dataward_skills_{month:%Y-%m}.csv",
            mime="text/csv",
        )

# ---- one skill in detail ---------------------------------------------------------------------
with skill_tab:
    ranked = dd.top_skills(demand, skills, month=dd.latest_month(demand), n=len(skills))
    names = ranked["canonical"].tolist() or sorted(skills["canonical"])
    name = st.selectbox("Навичка", names, key="skill_name")
    skill_id = skills.loc[skills["canonical"] == name, "skill_id"].iloc[0]
    trend = dd.skill_trend(demand, skill_id)
    declared = dd.skill_salary(salary, skill_id)

    cards = st.columns(3)
    if trend.empty:
        st.info("Цю навичку ще не знайдено в жодній вакансії.")
    else:
        last = trend.iloc[-1]
        with cards[0]:
            ui.kpi(
                1, "Частка вакансій", f"{last['share'] * 100:.1f}%",
                delta=f"місяць {last['month']:%m.%Y}", direction="neutral",
                help=f"{int(last['vacancies'])} з {int(last['month_vacancies'])} вакансій місяця",
            )  # fmt: skip
        with cards[1]:
            ui.kpi(2, "Вакансій за місяць", dd.fmt_int(last["vacancies"]))
        with cards[2]:
            if declared is None:
                ui.kpi(
                    3, "Медіана вилки, USD/міс", "—", delta="замало вакансій", direction="neutral"
                )
            else:
                ui.kpi(3, "Медіана вилки, USD/міс", dd.fmt_int(declared["median"]))

        with ui.card("Частка вакансій за місяцями"):
            if len(trend) > 1:
                ui.chart(
                    charts.share_trend(trend.rename(columns={"share": "value"})[["month", "value"]])
                )
            else:
                st.caption("Тренд з'явиться, коли накопичиться більше одного місяця.")

    ui.section("Зарплата за вакансіями з вилкою")
    if declared is None:
        st.info("Замало вакансій з указаною зарплатою, щоб показати число без шуму.")
    else:
        low, mid, high = st.columns(3)
        with low:
            ui.kpi(4, "p25, USD/міс", dd.fmt_int(declared["p25"]))
        with mid:
            ui.kpi(5, "Медіана, USD/міс", dd.fmt_int(declared["median"]))
        with high:
            ui.kpi(6, "p75, USD/міс", dd.fmt_int(declared["p75"]))
        st.caption(
            f"Вакансій з вилкою: {int(declared['vacancies'])}. Це лише ті, хто вказує зарплату, "
            "тож вибірка зміщена."
        )

    ui.section("З чим зустрічається")
    related = dd.related_skills(pairs, skills, skill_id)
    if related.empty:
        st.info("Недостатньо спільних вакансій для надійних пар.")
    else:
        st.dataframe(
            related.rename(
                columns={
                    "canonical": "Навичка",
                    "vacancies_together": "Разом у вакансіях",
                    "lift": "Lift",
                    "npmi": "NPMI",
                }
            ),  # fmt: skip
            hide_index=True,
            column_config={
                "NPMI": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
                "Lift": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        st.caption(
            "NPMI від −1 до 1: наскільки пара трапляється разом частіше, ніж випадково. "
            "Lift: у скільки разів частіше."
        )
    cluster = dd.skill_cluster(clusters, skills, skill_id)
    if cluster:
        st.markdown(
            f"**Стек «{cluster['label']}»** ({cluster['size']} навичок): "
            + ", ".join(cluster["members"])
        )

# ---- stacks ----------------------------------------------------------------------------------
with stacks_tab:
    st.caption(
        "Навички, які часто вимагають разом, об'єднано в кластери "
        "(метод Лувена на парах із високим NPMI)."
    )
    overview = dd.cluster_overview(clusters, skills)
    if overview.empty:
        st.info("Кластерів поки немає: потрібно більше вакансій.")
    else:
        st.dataframe(
            overview.rename(
                columns={"cluster_id": "№", "size": "Навичок", "label": "Ядро", "members": "Склад"}
            ),
            hide_index=True,
            height=320,
            column_config={
                "№": st.column_config.NumberColumn(width="small"),
                "Навичок": st.column_config.NumberColumn(width="small"),
                "Ядро": st.column_config.TextColumn(width="small"),
            },
        )
        options = {
            f"{row.cluster_id}. {row.label} ({row.size})": int(row.cluster_id)
            for row in overview.itertuples()
        }
        choice = st.selectbox("Стек", list(options), key="stack_choice")
        threshold = st.slider("Мінімальний NPMI зв'язку", 0.0, 1.0, 0.5, 0.05, key="stack_npmi")
        shown, qualified = dd.stack_edges(pairs, clusters, options[choice], min_npmi=threshold)
        note = "товщина лінії — сила зв'язку (NPMI від −1 до 1)."
        if qualified > len(shown):
            note += f" Показано {len(shown)} найсильніших зв'язків із {qualified}: підніміть поріг."
        with ui.card("Граф стеку", note):
            if shown.empty:
                st.info("За таким порогом зв'язків немає: знизьте його.")
            else:
                st.graphviz_chart(
                    dd.stack_dot(pairs, clusters, skills, options[choice], min_npmi=threshold)
                )
