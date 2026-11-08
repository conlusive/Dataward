from jobmarket.skill_clusters import cluster_skills

# two stacks tied inside, one weak bridge between them
PAIRS = [
    ("python", "django", 0.8),
    ("python", "flask", 0.7),
    ("django", "flask", 0.6),
    ("react", "typescript", 0.8),
    ("react", "redux", 0.7),
    ("redux", "typescript", 0.6),
    ("python", "react", 0.1),  # below the threshold: not an edge
]


def _groups(members: list) -> list[set[str]]:  # type: ignore[type-arg]
    by_cluster: dict[int, set[str]] = {}
    for member in members:
        by_cluster.setdefault(member.cluster_id, set()).add(member.skill_id)
    return [by_cluster[k] for k in sorted(by_cluster)]


def test_skills_asked_for_together_form_clusters_and_a_weak_pair_does_not_join_them() -> None:
    members = cluster_skills(PAIRS)

    groups = _groups(members)
    assert sorted(map(sorted, groups)) == [
        ["django", "flask", "python"],
        ["react", "redux", "typescript"],
    ]


def test_the_result_does_not_depend_on_the_order_of_the_pairs() -> None:
    assert cluster_skills(PAIRS) == cluster_skills(list(reversed(PAIRS)))


def test_each_member_carries_its_cluster_size_and_the_most_connected_skill_as_label() -> None:
    members = {m.skill_id: m for m in cluster_skills(PAIRS)}

    assert members["django"].cluster_size == 3
    assert {members[s].cluster_label for s in ("python", "django", "flask")} == {"python"}


def test_without_a_strong_pair_there_are_no_clusters() -> None:
    assert cluster_skills([("a", "b", 0.2), ("b", "c", -0.5)]) == []
    assert cluster_skills([]) == []
