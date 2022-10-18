# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_wSAA.ipynb.

# %% ../nbs/02_wSAA.ipynb 5
from __future__ import annotations
from fastcore.docments import *
from fastcore.test import *
from fastcore.utils import *

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from .basePredictor import BasePredictor, restructureWeightsDataList

# %% auto 0
__all__ = ['RandomForestWSAA', 'SAA']

# %% ../nbs/02_wSAA.ipynb 7
class RandomForestWSAA(RandomForestRegressor, BasePredictor):
    
    def fit(self, X, y):

        super(RandomForestRegressor, self).fit(X = X, y = y)
        
        self.y = y
        self.leafIndicesTrain = self.apply(X)
        

# %% ../nbs/02_wSAA.ipynb 10
@patch
def getWeightsData(self: RandomForestWSAA, 
                   X: np.ndarray, # Feature matrix of samples for which conditional density estimates are computed.
                   outputType: 'all' | # Specifies structure of output.
                               'onlyPositiveWeights' | 
                               'summarized' | 
                               'cumulativeDistribution' | 
                               'cumulativeDistributionSummarized' = 'onlyPositiveWeights', 
                   scalingList: list | np.ndarray | None = None, # List or array with same size as self.y containing floats being multiplied with self.y.
                   ):

    leafIndicesDf = self.apply(X)

    weightsDataList = list()

    for leafIndices in leafIndicesDf:
        leafComparisonMatrix = (self.leafIndicesTrain == leafIndices) * 1
        nObsInSameLeaf = np.sum(leafComparisonMatrix, axis = 0)

        # It can happen that RF decides that the best strategy is to fit no tree at
        # all and simply average all results (happens when min_child_sample is too high, for example).
        # In this case 'leafComparisonMatrix' mustn't be averaged because there has been only a single tree.
        if len(leafComparisonMatrix.shape) == 1:
            weights = leafComparisonMatrix / nObsInSameLeaf
        else:
            weights = np.mean(leafComparisonMatrix / nObsInSameLeaf, axis = 1)

        weightsPosIndex = np.where(weights > 0)[0]

        weightsDataList.append((weights[weightsPosIndex], weightsPosIndex))

    #---

    weightsDataList = restructureWeightsDataList(weightsDataList = weightsDataList, 
                                                 outputType = outputType, 
                                                 y = self.y, 
                                                 scalingList = scalingList,
                                                 equalWeights = False)

    return weightsDataList

# %% ../nbs/02_wSAA.ipynb 15
class SAA(BasePredictor):
    """SAA is a featureless approach that assumes the density of the target variable is given
    by assigning equal probability to each historical observation of said target variable."""
    
    def __init__(self):
        
        self.y = None
        
    def __str__(self):
        return "SAA()"
    __repr__ = __str__     
    

# %% ../nbs/02_wSAA.ipynb 17
@patch
def fit(self: SAA, 
        y: np.ndarray, # Target values which form the estimated density function based on the SAA algorithm.
        ):
    self.y = y

# %% ../nbs/02_wSAA.ipynb 19
@patch
def getWeightsData(self: SAA, 
                   X: np.ndarray, # Feature matrix for whose rows conditional density estimates are computed.
                   outputType: 'all' | # Specifies structure of output.
                               'onlyPositiveWeights' | 
                               'summarized' | 
                               'cumulativeDistribution' | 
                               'cumulativeDistributionSummarized' = 'onlyPositiveWeights', 
                   scalingList: list | np.ndarray | None = None, # List or array with same size as self.y containing floats being multiplied with self.y.
                   ):

    if X is None:
        neighborsList = [np.arange(len(self.y))]
    else:
        neighborsList = [np.arange(len(self.y)) for i in range(X.shape[0])]

    # weightsDataList is a list whose elements correspond to one test prediction each. 
    weightsDataList = [(np.repeat(1 / len(neighbors), len(neighbors)), np.array(neighbors)) for neighbors in neighborsList]

    weightsDataList = restructureWeightsDataList(weightsDataList = weightsDataList, 
                                                 outputType = outputType, 
                                                 y = self.y,
                                                 scalingList = scalingList,
                                                 equalWeights = True)

    return weightsDataList
