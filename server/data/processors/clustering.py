import operator
from collections import defaultdict
from typing import Tuple

from data import models
from data.processors import Modifier, GraphRepresentationType
from data.processors.ranking import build_edge_dict
import logging
import networkx as nx
from networkx.algorithms import community

logger = logging.getLogger('data.graph.clustering')


class GenericSingleEdgeAdder(Modifier):
    def __init__(self, *args, base_weight: float = None, edge_weight_type: str = None,
                 node_weight_type: str = None, **kwargs):
        """
        Merges Nodes sharing edges with weights in filter condition
        :param args:
        :param base_weight: base weight for new added edges
        :param node_weight_type: specified weight type
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.base_weight = self.conf_getfloat('base_weight', base_weight)
        self.node_weight_type = self.conf_get('node_weight_type', node_weight_type)
        self.edge_weight_type = self.conf_get('edge_weight_type', edge_weight_type)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'edge_weight_type={self.edge_weight_type}, edge_weight_type={self.node_weight_type} '
                     f'and base_weight={self.base_weight}')

    def modify(self, graph: GraphRepresentationType):
        def get_closest_node_to(node: Tuple[int, int]) -> Tuple[int, int]:
            this_relation_value = graph.comments[node[0]].splits[node[1]].wgts[self.node_weight_type]
            distances = []
            for c in graph.comments:
                if node[0] == graph.id2idx[c.id]:
                    continue
                for k, split in enumerate(c.splits):
                    candidate_node = (graph.id2idx[c.id], k)
                    distances.append((abs(this_relation_value-split.wgts[self.node_weight_type]), candidate_node))
            return min(distances)[1]

        edge_dict = build_edge_dict(graph)
        for comment in graph.comments:
            for j, comment_split in enumerate(comment.splits):
                this_node = (graph.id2idx[comment.id], j)
                node_edges = edge_dict[this_node]
                if node_edges is None or len(node_edges) == 0:
                    if j > 0:
                        other_node = (graph.id2idx[comment.id], 0)
                    else:
                        other_node = get_closest_node_to(this_node)
                    edge_weights = models.EdgeWeights()
                    edge_weights[self.edge_weight_type] = self.base_weight
                    graph.edges.append(models.Edge(src=this_node, tgt=other_node, wgts=edge_weights))


class GenericNodeMerger(Modifier):
    def __init__(self, *args, threshold: float = None, smaller_as: bool = None, edge_weight_type: str = None, **kwargs):
        """
        Merges Nodes sharing edges with weights in filter condition
        :param args:
        :param threshold: treshold for specified weight type
        :param smaller_as: direction for condition, less equals vs greater equals
        :param edge_weight_type: specified weight type
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.threshold = self.conf_getfloat('threshold', threshold)
        self.smaller_as = self.conf_getboolean('smaller_as', smaller_as)
        self.edge_weight_type = self.conf_get('edge_weight_type', edge_weight_type)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'threshold={self.threshold}, smaller_as={self.smaller_as} '
                     f'and edge_weight_type={self.edge_weight_type}')

    def modify(self, graph: GraphRepresentationType):
        if self.smaller_as:
            operator_filter = operator.le
        else:
            operator_filter = operator.ge

        look_up = {}
        reverse_look_up = defaultdict(set)
        cluster_id = 0

        for edge in graph.edges:
            if edge.wgts[self.edge_weight_type] is None:
                continue

            if operator_filter(edge.wgts[self.edge_weight_type], self.threshold):
                # use old id if existing, else increment
                if edge.tgt in look_up or edge.src in look_up:
                    src_cluster = look_up.get(edge.src)
                    tgt_cluster = look_up.get(edge.tgt)

                    if tgt_cluster != src_cluster:

                        if src_cluster is not None and tgt_cluster is None:
                            concrete_id = src_cluster
                        elif src_cluster is None and tgt_cluster is not None:
                            concrete_id = tgt_cluster
                        else:
                            # actual merge by replacing cluster ids in lookup tables
                            concrete_id = src_cluster
                            nodes_to_change = reverse_look_up[tgt_cluster]
                            for node in nodes_to_change:
                                look_up[node] = concrete_id
                                reverse_look_up[concrete_id].add(node)

                            del reverse_look_up[tgt_cluster]
                    else:
                        concrete_id = src_cluster
                else:
                    concrete_id = cluster_id
                    cluster_id += 1

                reverse_look_up[concrete_id].add(edge.tgt)
                reverse_look_up[concrete_id].add(edge.src)
                look_up[edge.tgt] = concrete_id
                look_up[edge.src] = concrete_id

        # merge preperation:
        negative_cluster_id = -1
        for comment in graph.comments:
            for j, split in enumerate(comment.splits):
                cluster = look_up.get((graph.id2idx[comment.id], j))
                # set id of nodes without cluster to -1
                if cluster is None:
                    cluster = negative_cluster_id
                    negative_cluster_id -= 1
                split.wgts.MERGE_ID = cluster

        return look_up, reverse_look_up


class SimilarityNodeMerger(GenericNodeMerger):
    def __init__(self, *args, threshold: float = None, smaller_as: bool = None, **kwargs):
        super().__init__(*args, threshold=threshold, edge_weight_type="SIMILARITY", smaller_as=smaller_as, **kwargs)


class ReplyToNodeMerger(GenericNodeMerger):
    def __init__(self, *args, threshold: float = None, smaller_as: bool = None, **kwargs):
        super().__init__(*args, threshold=threshold, edge_weight_type="REPLY_TO", smaller_as=smaller_as, **kwargs)


class SameCommentNodeMerger(GenericNodeMerger):
    def __init__(self, *args, threshold: float = None, smaller_as: bool = None, **kwargs):
        super().__init__(*args, threshold=threshold, edge_weight_type="SAME_COMMENT", smaller_as=smaller_as, **kwargs)


class SameArticleNodeMerger(GenericNodeMerger):
    def __init__(self, *args, threshold: float = None, smaller_as: bool = None, **kwargs):
        super().__init__(*args, threshold=threshold, edge_weight_type="SAME_ARTICLE", smaller_as=smaller_as, **kwargs)


class SameGroupNodeMerger(GenericNodeMerger):
    def __init__(self, *args, threshold: float = None, smaller_as: bool = None, **kwargs):
        super().__init__(*args, threshold=threshold, edge_weight_type="SAME_GROUP", smaller_as=smaller_as, **kwargs)


class TemporalNodeMerger(GenericNodeMerger):
    def __init__(self, *args, threshold: float = None, smaller_as: bool = None, **kwargs):
        super().__init__(*args, threshold=threshold, edge_weight_type="TEMPORAL", smaller_as=smaller_as, **kwargs)


class MultiNodeMerger(Modifier):
    def __init__(self, *args, reply_to_threshold=None, same_comment_threshold=None, same_article_threshold=None,
                 similarity_threshold=None, same_group_threshold=None, temporal_threshold=None, smaller_as=None,
                 conj_or=None, **kwargs):
        """
        Merges node based on multiple defined thresholds. Negative values indicate skips
        :param args:
        :param reply_to_threshold:
        :param same_comment_threshold:
        :param same_article_threshold:
        :param similarity_threshold:
        :param same_group_threshold:
        :param temporal_threshold:
        :param smaller_as: direction for condition, less equals vs greater equals
        :param conj_or: us as conj logical OR vs logical and
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.reply_to_threshold = self.conf_getfloat("reply_to_threshold", reply_to_threshold)
        self.same_comment_threshold = self.conf_getfloat("same_comment_threshold", same_comment_threshold)
        self.same_article_threshold = self.conf_getfloat("same_article_threshold", same_article_threshold)
        self.similarity_threshold = self.conf_getfloat("similarity_threshold", similarity_threshold)
        self.same_group_threshold = self.conf_getfloat("same_group_threshold", same_group_threshold)
        self.temporal_threshold = self.conf_getfloat("temporal_threshold", temporal_threshold)

        self.smaller_as = self.conf_getboolean('smaller_as', smaller_as)
        self.conj_or = self.conf_getboolean('conj_or', conj_or)

        self.threshold_dict = {"SIMILARITY": self.similarity_threshold,
                               "SAME_GROUP": self.same_group_threshold,
                               "TEMPORAL": self.temporal_threshold,
                               "SAME_ARTICLE": self.same_article_threshold,
                               "REPLY_TO": self.reply_to_threshold,
                               "SAME_COMMENT": self.same_comment_threshold}

        self.threshold_dict = {weight_type: threshold for weight_type, threshold in self.threshold_dict.items()
                               if threshold >= 0}

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'conj_or={self.conj_or}, smaller_as={self.smaller_as} '
                     f'and thresholds={self.threshold_dict}')

    def modify(self, graph: GraphRepresentationType):
        def loop_further_boolean(e):
            for weight_type, threshold in self.threshold_dict.items():
                temp_result = e.wgts[weight_type] is not None
                if self.conj_or and temp_result:
                    return True
                if not self.conj_or and not temp_result:
                    return False
            return not self.conj_or

        def filter_boolean(e, operator_func):
            for weight_type, threshold in self.threshold_dict.items():
                if e.wgts[weight_type] is None:
                    temp_result = False
                else:
                    temp_result = operator_func(e.wgts[weight_type], threshold)
                if self.conj_or and temp_result:
                    return True
                if not self.conj_or and not temp_result:
                    return False

            return not self.conj_or

        if self.smaller_as:
            operator_filter = operator.le
        else:
            operator_filter = operator.ge

        look_up = {}
        reverse_look_up = defaultdict(set)
        cluster_id = 0

        for edge in graph.edges:
            if not loop_further_boolean(edge):
                continue

            if filter_boolean(edge, operator_filter):
                # use old id if existing, else increment
                if edge.tgt in look_up or edge.src in look_up:
                    tgt_cluster = look_up.get(edge.tgt)
                    src_cluster = look_up.get(edge.src)

                    if tgt_cluster != src_cluster:

                        if src_cluster is not None and tgt_cluster is None:
                            concrete_id = src_cluster
                        elif src_cluster is None and tgt_cluster is not None:
                            concrete_id = tgt_cluster
                        else:
                            # actual merge by replacing cluster ids in lookup tables
                            concrete_id = src_cluster
                            nodes_to_change = reverse_look_up[tgt_cluster]
                            for node in nodes_to_change:
                                look_up[node] = concrete_id
                                reverse_look_up[concrete_id].add(node)

                            del reverse_look_up[tgt_cluster]
                    else:
                        concrete_id = src_cluster
                else:
                    concrete_id = cluster_id
                    cluster_id += 1

                reverse_look_up[concrete_id].add(edge.tgt)
                reverse_look_up[concrete_id].add(edge.src)
                look_up[edge.tgt] = concrete_id
                look_up[edge.src] = concrete_id

        # merge preperation:
        negative_cluster_id = -1
        for comment in graph.comments:
            for j, split in enumerate(comment.splits):
                cluster = look_up.get((graph.id2idx[comment.id], j))
                # set id of nodes without cluster to -1
                if cluster is None:
                    cluster = negative_cluster_id
                    negative_cluster_id -= 1
                split.wgts.MERGE_ID = cluster

        return look_up, reverse_look_up


class GenericClusterer(Modifier):
    def __init__(self, *args, edge_weight_type: str = None, algorithm: str = None, **kwargs):
        """
        Clusters nodes with the specified algorithm.
        :param args:
        :param edge_weight_type: edge weight type to use for clustering
        :param algorithm: girvanNewman vs greedyModularityCommunities (case insensitive)
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.edge_weight_type = self.conf_get('edge_weight_type', edge_weight_type)
        self.algorithm = self.conf_get('algorithm', algorithm)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'algorithm={self.algorithm} '
                     f'and edge_weight_type={self.edge_weight_type}')

    def modify(self, graph: GraphRepresentationType):
        look_up = {}
        reverse_look_up = defaultdict(set)
        networkx_graph = nx.Graph()

        for comment in graph.comments:
            for j, split in enumerate(comment.splits):
                networkx_graph.add_node(node_for_adding=(graph.id2idx[comment.id], j))

        for edge in graph.edges:
            if edge.wgts[self.edge_weight_type]:
                networkx_graph.add_edge(u_of_edge=edge.src, v_of_edge=edge.tgt, weight=edge.wgts[self.edge_weight_type])

        if self.algorithm.lower().endswith("girvannewman"):
            communities_generator = community.girvan_newman(networkx_graph)
            # parametrize?
            top_level_communities = next(communities_generator)
            # next_level_communities = next(communities_generator)
            communities = sorted(map(sorted, top_level_communities))
        else:
            communities = community.greedy_modularity_communities(networkx_graph)

        for cluster_id, found_community in enumerate(communities):
            for node in found_community:
                look_up[node] = cluster_id
                reverse_look_up[cluster_id].add(node)

        # clustering preperation:
        negative_cluster_id = -1
        for comment in graph.comments:
            for j, split in enumerate(comment.splits):
                cluster = look_up.get((graph.id2idx[comment.id], j))
                # set id of nodes without cluster to -1
                if cluster is None:
                    cluster = negative_cluster_id
                    negative_cluster_id -= 1
                split.wgts.CLUSTER_ID = cluster
        return look_up, reverse_look_up


class SimilarityClusterer(GenericClusterer):
    def __init__(self, *args, algorithm: str = None, **kwargs):
        super().__init__(*args, edge_weight_type="SIMILARITY", algorithm=algorithm, **kwargs)


class ReplyToClusterer(GenericClusterer):
    def __init__(self, *args, algorithm: str = None, **kwargs):
        super().__init__(*args, edge_weight_type="REPLY_TO", algorithm=algorithm, **kwargs)


class SameCommentClusterer(GenericClusterer):
    def __init__(self, *args, algorithm: str = None, **kwargs):
        super().__init__(*args, edge_weight_type="SAME_COMMENT", algorithm=algorithm, **kwargs)


class SameArticleClusterer(GenericClusterer):
    def __init__(self, *args, algorithm: str = None, **kwargs):
        super().__init__(*args, edge_weight_type="SAME_ARTICLE", algorithm=algorithm, **kwargs)


class SameGroupClusterer(GenericClusterer):
    def __init__(self, *args, algorithm: str = None, **kwargs):
        super().__init__(*args, edge_weight_type="SAME_GROUP", algorithm=algorithm, **kwargs)


class TemporalClusterer(GenericClusterer):
    def __init__(self, *args, algorithm: str = None, **kwargs):
        super().__init__(*args, edge_weight_type="TEMPORAL", algorithm=algorithm, **kwargs)


class MultiEdgeTypeClusterer(Modifier):
    def __init__(self, *args, use_reply_to: bool = None, use_same_comment: bool = None, use_same_article: bool = None,
                 use_similarity: bool = None, use_same_group: bool = None, use_temporal: bool = None,
                 algorithm: str = None, **kwargs):
        """
        Uses multiple edge Types for clustering of the specified algorithm
        :param args:
        :param use_reply_to:
        :param use_same_comment:
        :param use_same_article:
        :param use_similarity:
        :param use_same_group:
        :param use_temporal:
        :param algorithm: girvanNewman vs greedyModularityCommunities (case insensitive)
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.use_reply_to = self.conf_getboolean('use_reply_to', use_reply_to)
        self.use_same_comment = self.conf_getboolean('use_same_comment', use_same_comment)
        self.use_same_article = self.conf_getboolean('use_same_article', use_same_article)
        self.use_similarity = self.conf_getboolean('use_similarity', use_similarity)
        self.use_same_group = self.conf_getboolean('use_same_group', use_same_group)
        self.use_temporal = self.conf_getboolean('use_temporal', use_temporal)
        self.algorithm = self.conf_get('algorithm', algorithm)

        self.use_edge_types = set()
        if self.use_reply_to:
            self.use_edge_types.add("REPLY_TO")
        if self.use_same_comment:
            self.use_edge_types.add("SAME_COMMENT")
        if self.use_same_article:
            self.use_edge_types.add("SAME_ARTICLE")
        if self.use_similarity:
            self.use_edge_types.add("SIMILARITY")
        if self.use_same_group:
            self.use_edge_types.add("SAME_GROUP")
        if self.use_temporal:
            self.use_edge_types.add("TEMPORAL")

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'algorithm={self.algorithm}')

    def modify(self, graph: GraphRepresentationType):
        look_up = {}
        reverse_look_up = defaultdict(set)
        networkx_graph = nx.Graph()

        for comment in graph.comments:
            for j, split in enumerate(comment.splits):
                networkx_graph.add_node(node_for_adding=(graph.id2idx[comment.id], j))

        for edge in graph.edges:
            allow_add = False
            for edge_weight_type in self.use_edge_types:
                if edge.wgts[edge_weight_type]:
                    allow_add = True

            if allow_add:
                networkx_graph.add_edge(u_of_edge=edge.src, v_of_edge=edge.tgt, weights=edge.wgts)

        if self.algorithm.lower() == "girvannewman":
            communities_generator = community.girvan_newman(networkx_graph)
            # parametrize?
            top_level_communities = next(communities_generator)
            # next_level_communities = next(communities_generator)
            communities = sorted(map(sorted, top_level_communities))
        else:
            communities = community.greedy_modularity_communities(networkx_graph)

        for cluster_id, found_community in enumerate(communities):
            for node in found_community:
                look_up[node] = cluster_id
                reverse_look_up[cluster_id].add(node)

        # clustering preperation:
        negative_cluster_id = -1
        for comment in graph.comments:
            for j, split in enumerate(comment.splits):
                cluster = look_up.get((graph.id2idx[comment.id], j))
                # set id of nodes without cluster to -1
                if cluster is None:
                    cluster = negative_cluster_id
                    negative_cluster_id -= 1
                split.wgts.CLUSTER_ID = cluster

        return look_up, reverse_look_up
