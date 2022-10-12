# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/levelSetForecaster.ipynb.

# %% auto 0
__all__ = ['LevelSetForecaster', 'generateBins']

# %% ../nbs/levelSetForecaster.ipynb 5
import pandas as pd
import numpy as np

from sklearn.neighbors import NearestNeighbors 

from collections import Counter, defaultdict

from joblib import Parallel, delayed, dump, load

from .core import BaseWeightsBasedPredictor, restructureWeightsDataList

# %% ../nbs/levelSetForecaster.ipynb 7
class LevelSetForecaster(BaseWeightsBasedPredictor):
    
    def __init__(self, 
                 estimator, 
                 binSize = None):
        
        if not (hasattr(estimator, 'predict') and callable(estimator.predict)):
            raise ValueError("'estimator' has to have a 'predict'-method!")
        else:
            self.estimator = estimator
            
        if not (isinstance(binSize, (int, np.integer)) or binSize is None):
            raise ValueError("'binSize' has to be integer (or None if it is supposed to be tuned)!")
        else:
            self.binSize = binSize
        
        self.estimator = estimator
        self.binSize = binSize
        
        self.Y = None
        self.YPred = None
        self.binPerTrainPred = None
        self.indicesPerBin = None
        self.nearestNeighborsOnPreds = None
        
    #---        
    
    def fit(self, X, Y):
        
        YPredTrain = self.estimator.predict(X)
        
        binPerTrainPred, indicesPerBin = generateBins(binSize = self.binSize,
                                                      YPredTrain = YPredTrain)

        #---
        
        nn = NearestNeighbors(algorithm = 'kd_tree')
        YPredTrain_reshaped = np.reshape(YPredTrain, newshape = (len(YPredTrain), 1))

        nn.fit(X = YPredTrain_reshaped)
        
        #---
        
        self.Y = Y
        self.YPredTrain = YPredTrain
        self.binPerTrainPred = binPerTrainPred
        self.indicesPerBin = indicesPerBin
        self.nearestNeighborsOnPreds = nn
        
    #---
        
    def getWeightsData(self, X, outputType = 'onlyPositiveWeights', scalingList = None):
        
        binPerTrainPred = self.binPerTrainPred
        indicesPerBin = self.indicesPerBin
        nearestNeighborsOnPreds = self.nearestNeighborsOnPreds
        
        #---
        
        YPred = self.estimator.predict(X)   
        YPred_reshaped = np.reshape(YPred, newshape = (len(YPred), 1))
        
        nearestPredIndex = nearestNeighborsOnPreds.kneighbors(X = YPred_reshaped, 
                                                              n_neighbors = 1, 
                                                              return_distance = False).ravel()
        
        nearestPredNeighbor = self.YPredTrain[nearestPredIndex]

        neighborsList = [indicesPerBin[binPerTrainPred[nearestPredNeighbor[i]]] for i in range(len(YPred))]

        #---
        
        # Checks        
        for i in range(len(neighborsList)):
            if len(neighborsList[i]) < self.binSize:
                ipdb.set_trace()

        #---
        
        # weightsDataList is a list whose elements correspond to one test prediction each. 
        weightsDataList = [(np.repeat(1 / len(neighbors), len(neighbors)), np.array(neighbors)) for neighbors in neighborsList]

        weightsDataList = restructureWeightsDataList(weightsDataList = weightsDataList, 
                                                     outputType = outputType, 
                                                     Y = self.Y,
                                                     scalingList = scalingList,
                                                     equalWeights = True)

        return weightsDataList
    

# %% ../nbs/levelSetForecaster.ipynb 9
def generateBins(binSize, YPredTrain):
    
    """
    Used to generate the bin-structure induced by the Level-Set-Forecaster algorithm for
    ``neighborStrategy == 'bins'``.
    Bins are created by starting at the lowest value of YPredTrain and then succesively 
    adding the closest next prediction to the current bin until ``binSize``-many observations
    have been allocated. Then the generation of a new bin is started in the same manner
    until all values of YPredTrain have been assigned to exactly one bin.

    Parameters
    ----------
    binSize : int
        The size of each bin that is being created. Every bin is going to have this size
        apart from the one containing the predictions with the highest values (see remarks)
    YPredTrain : array
        The predictions for the training observations.

    Output
    ----------
    binPerPred : dict
        A dictionary whose keys are given by all unique values of YPredTrain.
        binPrePred[pred] returns the bin to which the current prediction 'pred'
        belongs to.
    indicesPerBin : dict
        A dictionary whose keys are given by all bins (the keys begin at zero).
        indicesPerBin[j] contains all indices of YPredTrain that belong to the same bin.

    Notes
    ----------
    The binning strategy leads to the bin of the highest prediction values being smaller
    than ``binSize``. As a convention, no bin is allowed to be smaller than ``binSize``.
    For that reason, the bin of the highest value is joined with the next bin to it, 
    so the final bin containing the highest prediction values is the only bin to contain
    more observations than ``binSize``.
    """
    
    YPredTrainUnique = pd.Series(YPredTrain).unique()
    predIndicesSort = np.argsort(YPredTrainUnique)
    
    YPredTrainUniqueSorted = YPredTrainUnique[predIndicesSort]
    indicesByPredTrain = [np.where(pred == YPredTrain)[0] for pred in YPredTrainUniqueSorted]
    
    currentBinSize = 0
    binIndex = 0
    binExisting = False
    trainIndicesLeft = len(YPredTrain)
    binPerPred = dict()
    indicesPerBin = dict()

    for i in range(len(indicesByPredTrain)):
        currentBinSize += len(indicesByPredTrain[i])
        binPerPred[YPredTrainUniqueSorted[i]] = binIndex
        
        if binExisting:
            indicesPerBin[binIndex] = np.append(indicesPerBin[binIndex], indicesByPredTrain[i])
        else:
            indicesPerBin[binIndex] = indicesByPredTrain[i]
            binExisting = True

        trainIndicesLeft -= len(indicesByPredTrain[i])
        if trainIndicesLeft < binSize:
            for j in np.arange(i+1, len(indicesByPredTrain), 1):
                binPerPred[YPredTrainUniqueSorted[j]] = binIndex
                indicesPerBin[binIndex] = np.append(indicesPerBin[binIndex], indicesByPredTrain[j])
            break

        if currentBinSize >= binSize:
            binIndex += 1
            currentBinSize = 0
            binExisting = False
    
    #---
    
    # Checks
    
    indices = np.array([])
    for k in range(len(indicesPerBin.keys())):
        indices = np.append(indices, indicesPerBin[k])
 
    if len(indices) != len(YPredTrain):
        ipdb.set_trace()
    
    predCheck = np.array([pred in binPerPred.keys() for pred in YPredTrain])
    keyCheck = np.array([key in YPredTrain for key in binPerPred.keys()])
    
    if (all(predCheck) & all(keyCheck)) is False:
        ipdb.set_trace()
    
    return binPerPred, indicesPerBin