from data.processors import Modifier
import data.models as models
from typing import List, Tuple, Dict
import logging
import numpy as np

logger = logging.getLogger('data.graph.comparator')


# class AModifiyer(Modifier):
#     def __init__(self, *args, base_weight=None, only_consecutive: bool = None, **kwargs):
#         """
#         Returns base_weight iff split_a and split_b are part of the same comment.
#         :param args:
#         :param base_weight: weight to attach
#         :param only_consecutive: only return weight of splits are consecutive
#         :param kwargs:
#         """
#         super().__init__(*args, **kwargs)
#         self.base_weight = self.conf_getfloat('base_weight', base_weight)
#         self.only_consecutive = self.conf_getboolean('only_consecutive', only_consecutive)
#
#         logger.debug(f'{self.__class__.__name__} initialised with '
#                      f'base_weight: {self.base_weight} and only_consecutive: {self.only_consecutive}')
#
#     @classmethod
#     def short_name(cls) -> str:
#         return 'sc'
#
#     @classmethod
#     def edge_type(cls) -> models.EdgeType:
#         return models.EdgeType.SAME_COMMENT
#
#     def modify(self, graph: models.Graph) -> models.Graph:
#         return graph

class PageRanker(Modifier):
    def pagerank(self, num_iterations: int = 100, d: float = 0.85, normalize=True):
        m = self.adjacence_matrix / self.adjacence_matrix.sum(axis=0, keepdims=1)
        n = m.shape[1]
        v = np.random.rand(n, 1)
        v = v / np.linalg.norm(v, 1)
        m_hat = (d * m + (1 - d) / n)
        for i in range(num_iterations):
            v = m_hat @ v
        ranks = {n.node_id: r[0] for n, r in zip(self.nodes, v)}

        ranks = {k: v for k, v in sorted(ranks.items(), key=lambda item: item[1], reverse=True)}

        if normalize:
            values = list(ranks.values())
            v_max = np.max(values)
            v_min = np.min(values)
            if v_max == v_min:
                v_min = -1 + v_max
            ranks = {k: (v - v_min) / (v_max - v_min) + 0.001 for k, v in ranks.items()}

        # update Graph
        for node in self.nodes:
            if node.weights is None:
                node.weights = {}

            node.weights["pagerank"] = ranks[node.node_id]

    def __init__(self, *args, base_weight=None, only_consecutive: bool = None, **kwargs):
        """
        Returns base_weight iff split_a and split_b are part of the same comment.
        :param args:
        :param base_weight: weight to attach
        :param only_consecutive: only return weight of splits are consecutive
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.base_weight = self.conf_getfloat('base_weight', base_weight)
        self.only_consecutive = self.conf_getboolean('only_consecutive', only_consecutive)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'base_weight: {self.base_weight} and only_consecutive: {self.only_consecutive}')

    @classmethod
    def short_name(cls) -> str:
        return 'sc'

    @classmethod
    def edge_type(cls) -> models.EdgeType:
        return models.EdgeType.SAME_COMMENT

    def modify(self, graph: models.Graph) -> models.Graph:
        return graph

class EdgeFilter(Modifier):
    def __init__(self, *args, base_weight=None, only_consecutive: bool = None, **kwargs):
        """
        Returns base_weight iff split_a and split_b are part of the same comment.
        :param args:
        :param base_weight: weight to attach
        :param only_consecutive: only return weight of splits are consecutive
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.base_weight = self.conf_getfloat('base_weight', base_weight)
        self.only_consecutive = self.conf_getboolean('only_consecutive', only_consecutive)

        logger.debug(f'{self.__class__.__name__} initialised with '
                     f'base_weight: {self.base_weight} and only_consecutive: {self.only_consecutive}')

    @classmethod
    def short_name(cls) -> str:
        return 'sc'

    @classmethod
    def edge_type(cls) -> models.EdgeType:
        return models.EdgeType.SAME_COMMENT

    def modify(self, graph: models.Graph) -> models.Graph:
        def within_thresholds(wgt_list: List[models.EdgeWeightType], thresholds: Dict[models.EdgeType, float]):
            for wgt in wgt_list:
                if wgt[0] < thresholds[wgt[1]]:
                    return False
            return True

        example_thresholds = {models.EdgeType.SAME_COMMENT: 0.7,
                              models.EdgeType.SAME_ARTICLE: 0.8,
                              models.EdgeType.SIMILARITY: 0.9,
                              models.EdgeType.SAME_GROUP: 0.1,
                              models.EdgeType.REPLY_TO: 0.8}

        graph.edges = [edge for edge in graph.edges if within_thresholds(edge.wgts, thresholds=example_thresholds)]
        return graph
    # def remove_edges(self, textual=0.8, structural=0.96, temporal=7200):
    #     # self.edges = [edge for edge in self.edges if edge.weights_bigger_as_threshold()]
    #     self.edges = [edge for edge in self.edges
    #                   if edge.weights["textual"] >= textual
    #                   and edge.weights["structural"] >= structural
    #                   and edge.weights["temporal"] <= temporal]
