# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_levelSetForecaster.ipynb.

# %% ../nbs/01_levelSetForecaster.ipynb 5
from __future__ import annotations
from fastcore.docments import *
from fastcore.test import *
from fastcore.utils import *

import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors 
from collections import Counter, defaultdict
from joblib import Parallel, delayed, dump, load

from .core import BaseWeightsBasedPredictor, restructureWeightsDataList

# %% auto 0
__all__ = ['LevelSetForecaster', 'generateBins', 'LevelSetForecaster_kNN', 'binSizeCV', 'scoresForFold', 'getCoefPres']

# %% ../nbs/01_levelSetForecaster.ipynb 7
class LevelSetForecaster(BaseWeightsBasedPredictor):
    """`LevelSetForecaster` turns any estimator that has a .predict-method into
    a condititional density estimator. The `LevelSetForecaster` class is supposed
    to be applied to estimators that have been fitted already."""
    
    def __init__(self, 
                 estimator, # (Fitted) object with a .predict-method.
                 binSize: int = None # Size of the bins created to group the training samples.
                 ):
        
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
    
    def __str__(self):
        return f"LevelSetForecaster(estimator = {self.estimator}, binSize = {self.binSize})"
    __repr__ = __str__      
    

# %% ../nbs/01_levelSetForecaster.ipynb 9
@patch
def fit(self:LevelSetForecaster, 
        X: np.ndarray, # Feature matrix used by 'estimator' to predict 'Y'.
        Y: np.ndarray, # 1-dimensional target variable corresponding to the features 'X'.
        ):

    if self.binSize > Y.shape[0]:
        raise ValueError("'binSize' mustn't be bigger than the size of 'Y'!")

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

# %% ../nbs/01_levelSetForecaster.ipynb 12
def generateBins(binSize: int, # Size of the bins of values being grouped together.
                 YPredTrain: np.ndarray, # 1-dimensional array of predicted values.
                 ):
    "Used to generate the bin-structure induced by the Level-Set-Forecaster algorithm"
    
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

# %% ../nbs/01_levelSetForecaster.ipynb 13
@patch
def getWeightsData(self: LevelSetForecaster, 
                   X: np.ndarray, # Feature matrix for whose rows conditional density estimates are computed.
                   outputType: 'all' | # Specifies structure of output.
                               'onlyPositiveWeights' | 
                               'summarized' | 
                               'cumulativeDistribution' | 
                               'cumulativeDistributionSummarized' = 'onlyPositiveWeights', 
                   scalingList: list | np.ndarray | None = None, # List or array with same size as self.Y containing floats being multiplied with self.Y.
                   ):
        
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

# %% ../nbs/01_levelSetForecaster.ipynb 16
class LevelSetForecaster_kNN(BaseWeightsBasedPredictor):
    
    def __init__(self, 
                 estimator, # Object with a .predict-method (fitted).
                 binSize: int | None = None, # Size of the neighbors considered to compute conditional density.
                 ):
        
        if not (hasattr(estimator, 'predict') and callable(estimator.predict)):
            raise ValueError("'estimator' has to have a 'predict'-method!")
        else:
            self.estimator = estimator
            
        if not isinstance(binSize, (int, np.integer)):
            raise ValueError("'binSize' has to be integer!")
        else:
            self.binSize = binSize
        
        self.estimator = estimator
        self.binSize = binSize
        
        self.Y = None
        self.YPred = None
        self.nearestNeighborsOnPreds = None
        
    #---
    
    def __str__(self):
        return f"LevelSetForecaster_kNN(estimator = {self.estimator}, binSize = {self.binSize})"
    __repr__ = __str__   
      

# %% ../nbs/01_levelSetForecaster.ipynb 18
@patch 
def fit(self:LevelSetForecaster_kNN, 
        X: np.ndarray, # Feature matrix used by 'estimator' to predict 'Y'.
        Y: np.ndarray, # Target variable corresponding to features 'X'.
        ):

    if self.binSize > Y.shape[0]:
        raise ValueError("'binSize' mustn't be bigger than the size of 'Y'!")

    YPredTrain = self.estimator.predict(X)
    YPredTrain_reshaped = np.reshape(YPredTrain, newshape = (len(YPredTrain), 1))

    nn = NearestNeighbors(algorithm = 'kd_tree')
    nn.fit(X = YPredTrain_reshaped)

    #---

    self.Y = Y
    self.YPredTrain = YPredTrain
    self.nearestNeighborsOnPreds = nn

# %% ../nbs/01_levelSetForecaster.ipynb 20
@patch
def getWeightsData(self: LevelSetForecaster_kNN, 
                   X: np.ndarray, # Feature matrix for whose rows conditional density estimates are computed.
                   outputType: 'all' | # Specifies structure of output.
                               'onlyPositiveWeights' | 
                               'summarized' | 
                               'cumulativeDistribution' | 
                               'cumulativeDistributionSummarized' = 'onlyPositiveWeights', 
                   scalingList: list | np.ndarray | None = None, # List or array with same size as self.Y containing floats being multiplied with self.Y.
                   ):

    nn = self.nearestNeighborsOnPreds

    #---

    YPred = self.estimator.predict(X)   
    YPred_reshaped = np.reshape(YPred, newshape = (len(YPred), 1))

    distancesDf, neighborsMatrix = nn.kneighbors(X = YPred_reshaped, 
                                                 n_neighbors = self.binSize + 1)

    #---

    neighborsList = list(neighborsMatrix[:, 0:self.binSize])
    distanceCheck = np.where(distancesDf[:, self.binSize - 1] == distancesDf[:, self.binSize])
    indicesToMod = distanceCheck[0]

    for index in indicesToMod:
        distanceExtremePoint = np.absolute(YPred[index] - self.YPredTrain[neighborsMatrix[index, self.binSize-1]])

        neighborsByRadius = nn.radius_neighbors(X = YPred_reshaped[index:index + 1], 
                                                radius = distanceExtremePoint, return_distance = False)[0]
        neighborsList[index] = neighborsByRadius

    #---

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

# %% ../nbs/01_levelSetForecaster.ipynb 23
class binSizeCV:

    def __init__(self,
                 estimator, # Object with a .predict-method (fitted).
                 cv, # Specifies cross-validation-splits. Identical to 'cv' used for cross-validation in sklearn.
                 LSF_type: 'LSF' | 'LSF_kNN', # Specifies which LSF-Object we work with during cross-validation.
                 binSizeGrid: list | np.ndarray = [4, 7, 10, 15, 20, 30, 40, 50, 60, 70, 80, 
                                                   100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800, 900,
                                                   1000, 1250, 1500, 1750, 2000, 2500, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000], # binSize (int) values being evaluated.                
                 probs: list | np.ndarray = [i / 100 for i in range(1, 100, 1)], # list or array of floats between 0 and 1. p-quantiles being predicted to evaluate performance of LSF.
                 refitPerProb: bool = False, # If True, for each p-quantile a fitted LSF with best binSize to predict it is returned. Otherwise only one LSF is returned that is best over all probs.
                 n_jobs: int | None = None, # number of folds being computed in parallel.
                 ):
        
        # CHECKS
        
        if isinstance(estimator, (LevelSetForecaster, LevelSetForecaster_kNN)):
            raise ValueError("'estimator' has to be a point predictor and not a LevelSetForecaster-Object!")   
        elif not (hasattr(estimator, 'predict') and callable(estimator.predict)):
            raise ValueError("'estimator' has to have a 'predict'-method!")
        else:
            self.estimator = estimator
            
        if LSF_type is None or not LSF_type in ["LSF", "LSF_kNN"]:
            raise ValueError("LSF_type must be specified and must either be 'LSF' or 'LSF_kNN'!")
        else:
            self.LSF_type = LSF_type
            
        if np.any(np.array(probs) > 1) or np.any(np.array(probs) < 0): 
            raise ValueError("probs must only contain numbers between 0 and 1!")
        else:
            self.probs = probs
        
        #---
        
        self.binSizeGrid = binSizeGrid        
        self.cv = cv
        self.refitPerProb = refitPerProb
        self.n_jobs = n_jobs
        
        self.best_binSize = None
        self.best_binSize_perProb = None
        self.best_estimatorLSF = None
        self.cv_results = None
        self.cv_results_raw = None
        

# %% ../nbs/01_levelSetForecaster.ipynb 25
@patch
def fit(self: binSizeCV, 
        X, 
        Y):
    
    scoresPerFold = Parallel(n_jobs = self.n_jobs)(delayed(scoresForFold)(cvFold = cvFold,
                                                                          binSizeGrid = self.binSizeGrid,
                                                                          probs = self.probs,
                                                                          estimator = self.estimator,
                                                                          LSF_type = self.LSF_type,
                                                                          Y = Y,
                                                                          X = X) for cvFold in cvFolds)    

    self.cv_results_raw = scoresPerFold

    #---

    nvCostsMatrix = scoresPerFold[0]

    for i in range(1, len(scoresPerFold)):
        nvCostsMatrix = nvCostsMatrix + scoresPerFold[i]

    nvCostsMatrix = nvCostsMatrix / len(cvFolds)

    self.cv_results = nvCostsMatrix

    #---

    meanCostsDf = nvCostsMatrix.mean(axis = 1)
    binSizeBestOverall = meanCostsDf.index[np.argmax(meanCostsDf)]
    self.best_binSize = binSizeBestOverall

    binSizeBestPerProb = nvCostsMatrix.idxmax(axis = 0)
    self.best_binSize_perProb = binSizeBestPerProb

    #---

    if self.refitPerProb:

        LSFDict = dict()
        for binSize in binSizeBestPerProb.unique():

            if self.LSF_type == 'LSF':
                LSF = LevelSetForecaster(estimator = self.estimator, 
                                         binSize = binSize)
            else:
                LSF = LevelSetForecaster_kNN(estimator = self.estimator, 
                                             binSize = binSize)

            LSF.fit(X = X, Y = Y)
            LSFDict[binSize] = LSF

        self.best_estimatorLSF = {prob: LSFDict[binSizeBestPerProb.loc[prob]] 
                                  for prob in binSizeBestPerProb.index}

    else:
        if self.LSF_type == 'LSF':
            LSF = LevelSetForecaster(estimator = self.estimator, 
                                     binSize = binSizeBestOverall)
        else:
            LSF = LevelSetForecaster_kNN(estimator = self.estimator, 
                                         binSize = binSizeBestOverall)

        LSF.fit(X = X, Y = Y)

        self.best_estimatorLSF = LSF

# %% ../nbs/01_levelSetForecaster.ipynb 28
# This function evaluates the newsvendor performance for different bin sizes for one specific fold.
# The considered bin sizes

def scoresForFold(cvFold, binSizeGrid, probs, estimator, LSF_type, Y, X):
   
    indicesTrain = cvFold[0]
    indicesTest = cvFold[1]
    
    YTrainFold = Y[indicesTrain]
    XTrainFold = X[indicesTrain]
    
    YTestFold = Y[indicesTest]
    XTestFold = X[indicesTest]
    
    estimator.fit(X = XTrainFold, y = YTrainFold)
    
    #---
       
    SAA_fold = SAA()
    SAA_fold.fit(Y = YTrainFold)
    
    # By setting 'X = None', the SAA results are only computed for a single observation (they are independent of X anyway).
    # In order to receive the final dataframe of SAA results, we simply duplicate this single row as many times as needed.
    quantilesDictSAAOneOb = SAA_fold.predict(X = None, probs = probs, outputAsDf = False)
    quantilesDictSAA = {prob: np.repeat(quantile, len(XTestFold)) for prob, quantile in quantilesDictSAAOneOb.items()}
    
    #---
                                                   
    coefPresPerBinSize = list()
    
    binSizeGrid = [binSize for binSize in binSizeGrid if binSize <= len(YTrainFold)]
    
    for binSize in iter(binSizeGrid):
        
        if LSF_type == 'LSF':
            estimatorLSF = LevelSetForecaster(estimator = estimator,
                                              binSize = binSize)
        else:
            estimatorLSF = LevelSetForecaster_kNN(estimator = estimator,
                                                  binSize = binSize)
        
        estimatorLSF.fit(X = XTrainFold,
                         Y = YTrainFold)
        
        quantilesDict = estimatorLSF.predict(X = XTestFold,
                                             probs = probs,
                                             outputAsDf = False)
        
        #---
        
        # coeffPres = Coefficient of Prescriptiveness
        
        coefPresDict = {prob: [] for prob in probs}
        
        for prob in probs:            
            coefPres = getCoefPres(decisions = quantilesDict[prob], 
                                   decisionsSAA = quantilesDictSAA[prob], 
                                   YTest = YTestFold, 
                                   prob = prob)
            
            coefPresDict[prob].append(coefPres)
    
    #---
    
    coefPresDf = pd.DataFrame(coefPresDict, index = binSizeGrid)
    
    return coefPresDf

# %% ../nbs/01_levelSetForecaster.ipynb 30
def getCoefPres(decisions, decisionsSAA, YTest, prob):

    # Newsvendor Costs of our model
    cost = np.array([prob * (YTest[i] - decisions[i]) if YTest[i] > decisions[i] 
                     else (1 - prob) * (decisions[i] - YTest[i]) 
                     for i in range(len(YTest))]).sum()
    
    # Newsvendor Costs of SAA
    costSAA = np.array([prob * (YTest[i] - decisionsSAA[i]) if YTest[i] > decisionsSAA[i] 
                        else (1 - prob) * (decisionsSAA[i] - YTest[i]) 
                        for i in range(len(YTest))]).sum()
    
    #---
    
    # We have to capture the special case of costSAA == 0, because then we can't compute the 
    # Coefficient of Prescriptiveness using the actual definition.
    if costSAA > 0:
        coefPres = 1 - cost / costSAA
    else:
        if cost == 0:
            coefPres = 1
        else:
            coefPres = 0
    
    return coefPres