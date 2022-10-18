# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_basePredictor.ipynb.

# %% ../nbs/00_basePredictor.ipynb 5
from __future__ import annotations
from fastcore.docments import *
from fastcore.test import *
from fastcore.utils import *

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from collections import Counter, defaultdict

# %% auto 0
__all__ = ['BasePredictor', 'restructureWeightsDataList', 'summarizeWeightsData']

# %% ../nbs/00_basePredictor.ipynb 7
class BasePredictor(ABC):
    """ 
    Base class that implements the 'prediction'-method for approaches based 
    on a reweighting of the empirical distribution.
    """
    
    @abstractmethod
    def __init__(self):
        """Define weights-based predictor"""
        
    def fit(self, X, y):
        """Fit weights-based predictor on training samples"""
        
    def getWeightsData(self, X):
        """Compute weights for every sample specified by feature matrix 'X'"""

    def predictQuantiles(self: BasePredictor, 
                         X: np.ndarray, # Feature matrix of samples for which conditional quantiles are computed.
                         probs: list | np.ndarray = [0.1, 0.5, 0.9], # Probabilities for which the estimated conditional p-quantiles are computed.
                         outputAsDf: bool = False, # Output is either a dataframe with 'probs' as cols or a dict with 'probs' as keys.
                         scalingList: list | np.ndarray | None = None, # List or array with same size as self.Y containing floats being multiplied with self.Y.
                         ):

        distributionDataList = self.getWeightsData(X = X,
                                                   outputType = 'cumulativeDistribution',
                                                   scalingList = scalingList)

        quantilesDict = {prob: [] for prob in probs}

        for probsDistributionFunction, yDistributionFunction in distributionDataList:

            for prob in probs:
                quantileIndex = np.where(probsDistributionFunction >= prob)[0][0]
                quantile = yDistributionFunction[quantileIndex]
                quantilesDict[prob].append(quantile)

        quantilesDf = pd.DataFrame(quantilesDict)

        # Just done to make the dictionary contain arrays rather than lists of the quantiles.
        quantilesDict = {prob: np.array(quantiles) for prob, quantiles in quantilesDict.items()}

        #---

        if outputAsDf:
            return quantilesDf

        else:
            return quantilesDict
    

# %% ../nbs/00_basePredictor.ipynb 12
def restructureWeightsDataList(weightsDataList, outputType = 'onlyPositiveWeights', y= None, scalingList = None, equalWeights = False):
    
    """
    Helper function. Creates weights-output by specifying considered
    neighbors of training observations for every test observation of interest.

    Parameters
    ----------
    neighborsList : {list}
        The i-th list-entry is supposed to correspond to the i-th test observation. 
        Every list-entry should be a array containing the indices of training observations
        which were selected as the neighbors of the considered test observation based on
        the selected Level-Set-Forecaster algorithm.     
    outputType : {"summarized", "onlyPositiveWeights", "all"}, default="onlyPositiveWeights"
        Specifies the structure of the output. 
        - If "all", then the weights are outputted as an array that is exactly as long as 
          the number of training observations. Consequently, also weights equal to zero are
          being computed. 
          NOTE: This can be take up lots of RAM for large datasets with
          > 10^6 observations.
        - If "onlyPositiveWeights", then weights equal to zero are truncated. In order to be 
          able to identify to which training observation each weight belongs, a tuple is
          outputted whose first entry are the weights and the second one are the corresponding
          training indices. 
        - If "summarized", then additionally to "onlyPositiveWeights", weights referencing to the
          same y-value are condensed to one single weight. In this case, the second entry of the
          outputted tuple contains the y-values to which each weight corresponds. 
          NOTE: Summarizing the weights can be very computationally burdensome if roughly the considered
          dataset has more than 10^6 observations and if ``binSize`` > 10^4.
        - If "cumulativeDistributionSummarized", then additionally to "summarized", the cumulative sum of the
          weights is computed, which can be interpreted as the empirical cumulative distribution
          function given the feature vector at hand.
          NOTE: This output type requires summarizing the weights, which can be very computationally 
          burdensome if roughly the considered dataset has more than 10^6 observations and if 
          ``binSize`` > 10^4.
    y: array, default=None
        The target values of the training observations. Only needed when ``outputType`` is given as 
        "all" or "summarized"."""
    
    if outputType == 'all':
        
        weightsDataListAll = list()
        
        for weights, indicesPosWeight in weightsDataList:
            weightsAll = np.zeros(len(y))
            weightsAll[indicesPosWeight] = weights
            weightsDataListAll.append(weightsAll)
        
        return weightsDataListAll
    
    #---
    
    elif outputType == 'onlyPositiveWeights':
        
        return weightsDataList
    
    #---
    
    elif outputType == 'summarized':
        
        weightsDataListSummarized = list()

        for i in range(len(weightsDataList)):
            weightsPos, yWeightPos = weightsDataList[i][0], y[weightsDataList[i][1]]
            
            weightsSummarized, yUnique = summarizeWeightsData(weightsPos = weightsPos, 
                                                              yWeightPos = yWeightPos,
                                                              equalWeights = equalWeights)
            
            if not scalingList is None:
                yUnique = yUnique * scalingList[i]
                
            weightsDataListSummarized.append((weightsSummarized, yUnique))
            
        return weightsDataListSummarized
    
    #---
    
    elif outputType == 'cumulativeDistribution':
        
        distributionDataList = list()
        
        for i in range(len(weightsDataList)):
            weightsPos, yWeightPos = weightsDataList[i][0], y[weightsDataList[i][1]]
            
            indicesSort = np.argsort(yWeightPos)
            
            weightsPosSorted = weightsPos[indicesSort]
            yWeightPosSorted = yWeightPos[indicesSort]
            
            cumulativeProbs = np.cumsum(weightsPosSorted)
            
            if not scalingList is None:
                yWeightPosSorted = yWeightPosSorted * scalingList[i]
                
            distributionDataList.append((cumulativeProbs, yWeightPosSorted))
            
        return distributionDataList
    
    #---
    
    elif outputType == 'cumulativeDistributionSummarized':
        
        distributionDataList = list()
        
        for i in range(len(weightsDataList)):
            weightsPos, yWeightPos = weightsDataList[i][0], y[weightsDataList[i][1]]
            
            weightsSummarizedSorted, yPosWeightUniqueSorted = summarizeWeightsData(weightsPos = weightsPos, 
                                                                                   yWeightPos = yWeightPos,
                                                                                   equalWeights = equalWeights)
            
            cumulativeProbs = np.cumsum(weightsSummarizedSorted)
            
            if not scalingList is None:
                yPosWeightUniqueSorted = yPosWeightUniqueSorted * scalingList[i]
                
            distributionDataList.append((cumulativeProbs, yPosWeightUniqueSorted))
            
        return distributionDataList
    

# %% ../nbs/00_basePredictor.ipynb 14
def summarizeWeightsData(weightsPos, yWeightPos, equalWeights = False):
    
    if equalWeights:
        counterDict = Counter(yWeightPos)
        yUniqueSorted = np.sort(list(counterDict.keys()))

        weightsSummarizedSorted = np.array([counterDict[value] / len(yWeightPos) for value in yUniqueSorted])
    
    else:
        duplicationDict = defaultdict(list)

        for i, item in enumerate(yWeightPos):
            duplicationDict[item].append(i)

        #---

        weightsSummarized = list()
        yUnique = list()

        for value, indices in duplicationDict.items():        

            weightsSummarized.append(weightsPos[indices].sum())
            yUnique.append(value)

        weightsSummarized, yUnique = np.array(weightsSummarized), np.array(yUnique)

        #---

        indicesSort = np.argsort(yUnique)
        weightsSummarizedSorted, yUniqueSorted = weightsSummarized[indicesSort], yUnique[indicesSort]
    
    return weightsSummarizedSorted, yUniqueSorted
