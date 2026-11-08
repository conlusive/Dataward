"""Groups of skills that tend to be asked for together (Louvain communities on the pair graph).

Input is the `fct_skill_pairs` mart: an edge between two skills weighted by their normalised PMI.
Only strong pairs become edges (`MIN_NPMI`), so a skill that is merely common (Git, Docker) does not
glue unrelated stacks into one cluster. The result is deterministic: fixed seed, and clusters are
numbered by size and then by their first skill.
"""

from dataclasses import dataclass

import networkx as nx

MIN_NPMI = 0.3
SEED = 42


@dataclass(frozen=True)
class ClusterMember:
    skill_id: str
    cluster_id: int
    cluster_size: int
    cluster_label: str  # the member most strongly tied to the others


def cluster_skills(
    pairs: list[tuple[str, str, float]], *, min_npmi: float = MIN_NPMI
) -> list[ClusterMember]:
    """pairs: (skill_a, skill_b, npmi). Skills with no strong pair are not in any cluster."""
    graph: nx.Graph = nx.Graph()
    for skill_a, skill_b, npmi in pairs:
        if npmi >= min_npmi:
            graph.add_edge(skill_a, skill_b, weight=npmi)
    if graph.number_of_edges() == 0:
        return []

    communities = [
        sorted(members)
        for members in nx.community.louvain_communities(graph, weight="weight", seed=SEED)
        if len(members) >= 2
    ]
    communities.sort(key=lambda members: (-len(members), members[0]))

    result: list[ClusterMember] = []
    for cluster_id, members in enumerate(communities, start=1):
        strength = {m: graph.degree(m, weight="weight") for m in members}
        label = min(members, key=lambda m: (-strength[m], m))
        result.extend(ClusterMember(m, cluster_id, len(members), label) for m in members)
    return result
