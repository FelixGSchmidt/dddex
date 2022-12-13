# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_CrossValidation.ipynb.

# %% ../nbs/04_CrossValidation.ipynb 4
from __future__ import annotations
from fastcore.docments import *
from fastcore.test import *
from fastcore.utils import *

import pandas as pd
import numpy as np

from joblib import Parallel, delayed, dump, load
from collections import defaultdict
import copy

from sklearn.model_selection import ParameterGrid, ParameterSampler
from sklearn.base import clone

from .baseClasses import BaseLSx
from .wSAA import SampleAverageApproximation

# %% auto 0
__all__ = ['QuantileCrossValidation', 'getFoldScore', 'CrossValidationLSx_combined', 'getFoldScore_combined', 'getCostRatio',
           'groupedTimeSeriesSplit']

# %% ../nbs/04_CrossValidation.ipynb 6
class QuantileCrossValidation:
    """
    Class to efficiently tune the `binSize` parameter of all Level-Set based models.
    """
    
    def __init__(self,
                 # An object with a `predict` method that must (!) have an argument called `probs`
                 # that specifies which quantiles to predict. Further, `quantileEstimator` needs
                 # a `set_params` and `fit` method.
                 quantileEstimator, 
                 cvFolds, # An iterable yielding (train, test) splits as arrays of indices.
                 # dict or list of dicts with parameters names (`str`) as keys and distributions
                 # or lists of parameters to try. Distributions must provide a ``rvs``
                 # method for sampling (such as those from scipy.stats.distributions).
                 parameterGrid: dict, 
                 randomSearch: bool=False, # Whether to use randomized search or grid search
                 # Number of parameter settings that are sampled if `randomSearch == True`. 
                 # n_iter trades off runtime vs quality of the solution.
                 nIter: int=None,
                 # iterable of floats between 0 and 1. These determine the p-quantiles being predicted 
                 # to evaluate performance of each parameter setting.
                 probs: list=[i / 100 for i in range(1, 100, 1)],
                 # If True, for each p-quantile a fitted LSF with best binSize to predict it is returned. 
                 # Otherwise only one LSF is returned that is best over all probs.
                 refitPerProb: bool=False, 
                 n_jobs: int=None, # Number of jobs to run in parallel.
                 # Pseudo random number generator state used for random uniform sampling of parameter candidate values.
                 # Pass an int for reproducible output across multiple function calls.
                 random_state: int=None, 
                 ):
        
        # CHECKS  
        # if not isinstance(estimatorLSx, (BaseLSx)):
        #     raise ValueError("'estimatorLSx' has to be a 'LevelSetKDEx', 'LevelSetKDEx_NN_new' or a 'LevelSetKDEx_kNN' object!")               
        
        if np.any(np.array(probs) > 1) or np.any(np.array(probs) < 0): 
            raise ValueError("probs must only contain numbers between 0 and 1!") 
        
        #---
        
        if randomSearch:
            self.parameterGrid = ParameterSampler(param_distributions = parameterGrid,
                                                  n_iter = nIter,
                                                  random_state = random_state)
            
            self.randomSearch = True
            self.nIter = nIter
            self.random_state = random_state
            
        else:
            self.parameterGrid = ParameterGrid(parameterGrid)
            self.randomSearch = False
            
        #---
        
        self.quantileEstimator = copy.deepcopy(quantileEstimator)
        self.cvFolds = cvFolds
        self.probs = probs
        self.refitPerProb = refitPerProb
        self.n_jobs = n_jobs
        
        self.bestParams = None
        self.bestParams_perProb = None
        self.bestEstimator = None
        self.bestEstimator_perProb = None
        self.cvResults = None
        self.cvResults_raw = None
        

# %% ../nbs/04_CrossValidation.ipynb 7
@patch
def fit(self: QuantileCrossValidation, 
        X: np.ndarray, # Feature matrix (has to work with the folds specified via `cvFolds`)
        y: np.ndarray, # Target values (has to work with the folds specified via `cvFolds`)
        ): 
    
    # Making sure that X and y are arrays to ensure correct subsetting via implicit indices.
    X = np.array(X)
    y = np.array(y)
    
    scoresPerFold = Parallel(n_jobs = self.n_jobs)(delayed(getFoldScore)(quantileEstimator = copy.deepcopy(self.quantileEstimator),
                                                                         parameterGrid = self.parameterGrid,
                                                                         cvFold = cvFold,
                                                                         probs = self.probs,
                                                                         X = X,
                                                                         y = y) for cvFold in self.cvFolds)
    
    # scoresPerFold = [getFoldScore(quantileEstimator = copy.deepcopy(self.quantileEstimator),
    #                               parameterGrid = self.parameterGrid,
    #                               cvFold = cvFold,
    #                               probs = self.probs,
    #                               y = y,
    #                               X = X) for cvFold in self.cvFolds]

    self.cvResults_raw = scoresPerFold
    meanCostsDf = sum(scoresPerFold) / len(scoresPerFold)
    self.cvResults = meanCostsDf
    
    #---
    
    # BEST PARAMETER SETTINGS OVER ALL PROBS
    meanCostsPerParam = meanCostsDf.mean(axis = 1)
    paramsBest = meanCostsPerParam.index[np.argmin(meanCostsPerParam)]
    paramsBest = dict(zip(meanCostsPerParam.index.names, paramsBest))
    self.bestParams = paramsBest
    
    #---
    
    # BEST PARAMETER SETTINGS PER PROB
    paramsBestPerProbSeries = meanCostsDf.idxmin(axis = 0)
    paramsBestPerProb = {prob: dict(zip(meanCostsDf.index.names, paramsBestPerProbSeries.loc[prob])) for prob in self.probs}
    self.bestParams_perProb = paramsBestPerProb
    
    #---
    
    # REFITTING ESTIMATORS
    if self.refitPerProb:      
        
        # GET UNIQUE PARAMETER COMBS OF LSx THAT ARE BEST FOR ANY PROB
        paramsUnique = pd.DataFrame(paramsBestPerProb.values()).drop_duplicates().to_dict(orient = 'records')
        estimatorDict = dict()
        
        for params in paramsUnique:
            quantileEstimator = copy.deepcopy(self.quantileEstimator)
            quantileEstimator.set_params(**params)
            
            quantileEstimator.fit(X = X, y = y)
            estimatorDict[tuple(params.values())] = quantileEstimator
        
        #---
        
        # DICTIONARY OF THE BEST LSx-ESTIMATORS PER PROB
        bestEstimatorPerProb = {prob: estimatorDict[tuple(paramsBestPerProb[prob].values())] for prob in self.probs}
        self.bestEstimator_perProb = bestEstimatorPerProb
        
    #---
    
    quantileEstimator = copy.deepcopy(self.quantileEstimator)
    quantileEstimator.set_params(**paramsBest)
    quantileEstimator.fit(X = X, y = y)

    self.bestEstimator = quantileEstimator

# %% ../nbs/04_CrossValidation.ipynb 9
# This function evaluates the newsvendor performance for different bin sizes for one specific fold.
# The considered bin sizes

def getFoldScore(quantileEstimator, parameterGrid, cvFold, probs, X, y):
    
    indicesTrain = cvFold[0]
    indicesTest = cvFold[1]
    
    yTrainFold = y[indicesTrain]
    XTrainFold = X[indicesTrain]
    
    yTestFold = y[indicesTest]
    XTestFold = X[indicesTest]
    
    #---

    SAA_fold = SampleAverageApproximation()
    SAA_fold.fit(y = yTrainFold)

    # By setting 'X = None', the SAA results are only computed for a single observation (they are independent of X anyway).
    # In order to receive the final dataframe of SAA results, we simply duplicate this single row as many times as needed.
    quantilesSAA = SAA_fold.predict(X = None, probs = probs, outputAsDf = True)
    quantilesDfSAA = pd.concat([quantilesSAA] * XTestFold.shape[0], axis = 0).reset_index(drop = True)

    #---
    
    # Necessary to ensure compatability with wSAA-models etc.
    try:
        quantileEstimator.refitPointEstimator(X = XTrainFold, 
                                              y = yTrainFold)
    except:
        pass

    costsPerParam = defaultdict(dict)

    for params in parameterGrid:

        quantileEstimator.set_params(**params)

        quantileEstimator.fit(X = XTrainFold,
                              y = yTrainFold)

        quantilesDf = quantileEstimator.predict(X = XTestFold,
                                                probs = probs,
                                                outputAsDf = True)

        costsDict = {prob: getCostRatio(decisions = quantilesDf.loc[:, prob], 
                                            decisionsSAA = quantilesDfSAA.loc[:, prob], 
                                            yTest = yTestFold, 
                                            prob = prob) for prob in probs}

        costsPerParam[tuple(params.values())] = costsDict

    #---

    costsDf = pd.DataFrame.from_dict(costsPerParam, orient = 'index')
    costsDf.index.names = list(params.keys())
    
    return costsDf

# %% ../nbs/04_CrossValidation.ipynb 11
class CrossValidationLSx_combined:
    """
    Class to efficiently tune the `binSize` parameter of all Level-Set based models.
    """
    
    def __init__(self,
                 estimatorLSx, # A Level-Set based model.
                 cvFolds, # An iterable yielding (train, test) splits as arrays of indices.
                 # dict or list of dicts with LSx parameters names (`str`) as keys and distributions
                 # or lists of parameters to try. Distributions must provide a ``rvs``
                 # method for sampling (such as those from scipy.stats.distributions).
                 parameterGridLSx: dict,
                 # dict or list of dicts with parameters names (`str`) of the point predictor as keys
                 # and distributions or lists of parameters to try. Distributions must provide a ``rvs``
                 # method for sampling (such as those from scipy.stats.distributions).
                 parameterGridEstimator: dict,
                 randomSearchLSx: bool=False, # Whether to use randomized search or grid search for the LSx parameters.
                 # Whether to use randomized search or grid search for the point predictor parameters.
                 randomSearchEstimator: bool=False, 
                 # Number of parameter settings of the LSx model that are sampled if `randomSearchLSx == True`. 
                 # LSx parameter settings are usually relatively cheap to evaluate, so all sampled LSx paramater settings
                 # are evaluated for each point predictor parameter setting.
                 nIterLSx: int=None,
                 # Number of parameter settings of the underlying point predictor that are sampled if 
                 # `randomSearchEstimator == True`. nIterEstimator trades off runtime vs quality of the solution.
                 nIterEstimator: int=None,
                 # iterable of floats between 0 and 1. These determine the p-quantiles being predicted 
                 # to evaluate performance of each parameter setting.
                 probs: list=[i / 100 for i in range(1, 100, 1)], 
                 # If True, for each p-quantile a fitted LSF with best binSize to predict it is returned. 
                 # Otherwise only one LSF is returned that is best over all probs.
                 refitPerProb: bool=False, 
                 n_jobs: int=None, # number of folds being computed in parallel.
                 # Pseudo random number generator state used for random uniform sampling of parameter candidate values.
                 # Pass an int for reproducible output across multiple function calls.
                 random_state: int=None,
                 ):
        
        # CHECKS  
        if not isinstance(estimatorLSx, (BaseLSx)):
            raise ValueError("'estimatorLSx' has to be a 'LevelSetKDEx', 'LevelSetKDEx_NN_new' or a 'LevelSetKDEx_kNN' object!")
            
        if len(parameterGridEstimator) == 0:
            raise ValueError("No parameter candidates have been specified for the point predictor. If you want to only evaluate"
                             "parameter settings of the LSx-estimator itself, use the class `QuantileCrossValidation` instead or"
                             "provide a fixed parameter setting for the point predictor via `parameterGridEstimator`.")
            
        if len(parameterGridLSx) == 0:
            raise ValueError("No parameter candidates have been specified for the LSx model! If you want to only evaluate"
                             "parameter settings of the point predictor, use standard cross-validation classes or instead"
                             "provide a fixed parameter setting for the LS model via `parameterGridLSx`.")
            
        if np.any(np.array(probs) > 1) or np.any(np.array(probs) < 0): 
            raise ValueError("`probs` must only contain numbers between 0 and 1!")
            
        if len(probs) == 0:
            raise ValueError("`probs` must be specified!")
        
        #---
        
        if randomSearchLSx:
            self.parameterGridLSx = ParameterSampler(param_distributions = parameterGridLSx,
                                                     n_iter = nIterLSx,
                                                     random_state = random_state)
            self.randomSearchLSx = True
            self.nIterLsx = nIterLSx
            self.random_state = random_state
        
        else:
            self.parameterGridLSx = ParameterGrid(parameterGridLSx)
            self.randomSearchLSx = False
            
        
        if randomSearchEstimator:
            
            self.parameterGridEstimator = ParameterSampler(param_distributions = parameterGridEstimator,
                                                           n_iter = nIterEstimator,
                                                           random_state = random_state)
            self.randomSearchEstimator = True
            self.nIterEstimator = nIterEstimator
            self.random_state = random_state
            
        else:
            self.parameterGridEstimator = ParameterGrid(parameterGridEstimator)
            self.randomSearchEstimator = False
            
        #---
        
        self.estimatorLSx = copy.deepcopy(estimatorLSx)
        
        self.cvFolds = cvFolds
        self.probs = probs
        self.refitPerProb = refitPerProb
        self.n_jobs = n_jobs
        
        self.bestParams = None
        self.bestParams_perProb = None
        self.bestEstimatorLSx = None
        self.bestEstimatorLSx_perProb = None
        self.cvResults = None
        self.cvResults_raw = None
        

# %% ../nbs/04_CrossValidation.ipynb 12
@patch
def fit(self: CrossValidationLSx_combined, 
        X: np.ndarray, # Feature matrix (has to work with the folds specified via `cvFolds`)
        y: np.ndarray, # Target values (has to work with the folds specified via `cvFolds`)
        ): 
    
    # Making sure that X and y are arrays to ensure correct subsetting via implicit indices.
    X = np.array(X)
    y = np.array(y)
    
    scoresPerFold = Parallel(n_jobs = self.n_jobs)(delayed(getFoldScore_combined)(estimatorLSx = copy.deepcopy(self.estimatorLSx),
                                                                                  parameterGridLSx = self.parameterGridLSx, 
                                                                                  parameterGridEstimator = self.parameterGridEstimator,
                                                                                  cvFold = cvFold,
                                                                                  probs = self.probs,
                                                                                  y = y,
                                                                                  X = X) for cvFold in self.cvFolds)
    
    # scoresPerFold = [getFoldScore_combined(estimatorLSx = copy.deepcopy(self.estimatorLSx),
    #                                        parameterGridLSx = self.parameterGridLSx,
    #                                        parameterGridEstimator = self.parameterGridEstimator,
    #                                        cvFold = cvFold,
    #                                        probs = self.probs,
    #                                        y = y,
    #                                        X = X) for cvFold in self.cvFolds]

    self.cvResults_raw = scoresPerFold
    meanCostsDf = sum(scoresPerFold) / len(scoresPerFold)
    self.cvResults = meanCostsDf
    
    #---
    
    # BEST PARAMETER SETTINGS OVER ALL PROBS
    meanCostsPerParam = meanCostsDf.mean(axis = 1)
    paramsBest = meanCostsPerParam.index[np.argmin(meanCostsPerParam)]
    paramsBest = dict(zip(meanCostsPerParam.index.names, paramsBest))
    
    paramsLSxNames = self.estimatorLSx._get_param_names()
    paramsLSxBest = {paramName: value for paramName, value in paramsBest.items() if paramName in paramsLSxNames}
    paramsEstimatorBest = {paramName: value for paramName, value in paramsBest.items() if not paramName in paramsLSxNames}
    
    self.bestParams = paramsBest
    self.bestParamsLSx = paramsLSxBest
    self.bestParamsEstimator = paramsEstimatorBest
    
    #---
    
    # BEST PARAMETER SETTINGS PER PROB
    paramsBestPerProbSeries = meanCostsDf.idxmin(axis = 0)
    paramsBestPerProb = {prob: dict(zip(meanCostsDf.index.names, paramsBestPerProbSeries.loc[prob])) for prob in self.probs}
    
    paramsLSxBestPerProb = {prob: {paramName: value for paramName, value in paramsBestPerProb[prob].items() 
                                   if paramName in paramsLSxNames} for prob in self.probs}
    paramsEstimatorBestPerProb = {prob: {paramName: value for paramName, value in paramsBestPerProb[prob].items() 
                                   if not paramName in paramsLSxNames} for prob in self.probs}
    
    self.bestParams_perProb = paramsBestPerProb
    self.bestParamsLSx_perProb = paramsBestPerProb
    self.bestParamsEstimator_perProb = paramsBestPerProb
    
    #---
    
    # REFITTING ESTIMATORS
    if self.refitPerProb:
        
        # GET UNIQUE PARAMETER COMBS OF ESTIMATOR THAT ARE BEST FOR ANY PROB
        paramsEstimatorUnique = pd.DataFrame(paramsEstimatorBestPerProb.values()).drop_duplicates().to_dict(orient = 'records')
        estimatorDict = dict()
        
        for params in paramsEstimatorUnique:
            estimator = clone(self.estimatorLSx.estimator)
            estimator.set_params(**params)
            estimator.fit(X = X, y = y)
            estimatorDict[tuple(params.values())] = estimator
        
        #---
        
        # GET UNIQUE PARAMETER COMBS OF LSx THAT ARE BEST FOR ANY PROB
        paramsUnique = pd.DataFrame(paramsBestPerProb.values()).drop_duplicates().to_dict(orient = 'records')
        
        estimatorLSxDict = dict()
        for params in paramsUnique:
            paramsLSx = {paramName: value for paramName, value in params.items() if paramName in paramsLSxNames}
            paramsEstimatorTuple = tuple(value for paramName, value in params.items() if not paramName in paramsLSxNames)
            
            estimator = estimatorDict[paramsEstimatorTuple]
            estimatorLSx = copy.deepcopy(self.estimatorLSx)
            
            estimatorLSx.set_params(**paramsLSx, 
                                    estimator = estimator)
            
            estimatorLSx.fit(X = X, y = y)
            estimatorLSxDict[tuple(params.values())] = estimatorLSx
        
        #---
        
        # DICTIONARY OF THE BEST LSx-ESTIMATORS PER PROB
        bestEstimatorPerProb = {prob: estimatorLSxDict[tuple(paramsBestPerProb[prob].values())] for prob in self.probs}
        self.bestEstimatorLSx_perProb = bestEstimatorPerProb
        
    #---
    
    estimatorLSx = copy.deepcopy(self.estimatorLSx)
    
    estimator = clone(estimatorLSx.estimator)
    estimator.set_params(**paramsEstimatorBest)
    estimator.fit(X = X, y = y)
    
    estimatorLSx.set_params(**paramsLSxBest,
                            estimator = estimator)
    estimatorLSx.fit(X = X, y = y)

    self.bestEstimatorLSx = estimatorLSx

# %% ../nbs/04_CrossValidation.ipynb 15
# This function evaluates the newsvendor performance for different bin sizes for one specific fold.
# The considered bin sizes

def getFoldScore_combined(estimatorLSx, parameterGridLSx, parameterGridEstimator, cvFold, probs, X, y):
    
    indicesTrain = cvFold[0]
    indicesTest = cvFold[1]
    
    yTrainFold = y[indicesTrain]
    XTrainFold = X[indicesTrain]
    
    yTestFold = y[indicesTest]
    XTestFold = X[indicesTest]
    
    #---

    SAA_fold = SampleAverageApproximation()
    SAA_fold.fit(y = yTrainFold)

    # By setting 'X = None', the SAA results are only computed for a single observation (they are independent of X anyway).
    # In order to receive the final dataframe of SAA results, we simply duplicate this single row as many times as needed.
    quantilesSAA = SAA_fold.predict(X = None, probs = probs, outputAsDf = True)
    quantilesDfSAA = pd.concat([quantilesSAA] * XTestFold.shape[0], axis = 0).reset_index(drop = True)
    
    #---
    
    costsDfList = list()
    
    for paramsEstimator in parameterGridEstimator:
        
        estimatorLSx.refitPointEstimator(X = XTrainFold, 
                                         y = yTrainFold,
                                         **paramsEstimator)

        #---

        costsPerParamLSx = defaultdict(dict)

        for paramsLSx in parameterGridLSx:

            estimatorLSx.set_params(**paramsLSx)

            estimatorLSx.fit(X = XTrainFold,
                             y = yTrainFold)

            quantilesDf = estimatorLSx.predict(X = XTestFold,
                                                 probs = probs,
                                                 outputAsDf = True)

            #---
            
            costsDict = {prob: getCostRatio(decisions = quantilesDf.loc[:, prob], 
                                            decisionsSAA = quantilesDfSAA.loc[:, prob], 
                                            yTest = yTestFold, 
                                            prob = prob) for prob in probs}
            
            costsPerParamLSx[tuple(paramsLSx.values())] = costsDict

        #---
        
        costsDf = pd.DataFrame.from_dict(costsPerParamLSx, orient = 'index')
        
        paramsLSxNames = list(paramsLSx.keys())
        costsDf.index.names = paramsLSxNames

        costsDf = costsDf.reset_index(drop = False)
        for paramName, value in paramsEstimator.items():
            costsDf[paramName] = value

        paramNames = paramsLSxNames + list(paramsEstimator.keys())
        costsDf = costsDf.set_index(paramNames)
        
        costsDfList.append(costsDf)
        
    #---
    
    costsDf = pd.concat(costsDfList, axis = 0)
    
    return costsDf

# %% ../nbs/04_CrossValidation.ipynb 18
def getCostRatio(decisions, decisionsSAA, yTest, prob):

    # Newsvendor Costs of our model
    cost = np.array([prob * (yTest[i] - decisions[i]) if yTest[i] > decisions[i] 
                     else (1 - prob) * (decisions[i] - yTest[i]) 
                     for i in range(len(yTest))]).sum()
    
    # Newsvendor Costs of SAA
    costSAA = np.array([prob * (yTest[i] - decisionsSAA[i]) if yTest[i] > decisionsSAA[i] 
                        else (1 - prob) * (decisionsSAA[i] - yTest[i]) 
                        for i in range(len(yTest))]).sum()
    
    #---
    
    # We have to capture the special case of costSAA == 0, because then we can't compute the 
    # Cost-Ratio using the actual definition.
    if costSAA > 0:
        costRatio = cost / costSAA
    else:
        if cost == 0:
            costRatio = 0
        else:
            costRatio = 1
    
    return costRatio

# %% ../nbs/04_CrossValidation.ipynb 20
# This function creates the cross-validation folds for every time series. Usually you'd want all test-observations 
# of each fold to refer to the same time period, but this is impossible to ensure in the case of the two-step models,
# because the regression of the non-zero observations will always contain data of different time points. For that
# reason, we refrain from trying to ensure this consistency.
# Instead we organize our splits such that we always move a fixed amount of observations into the future from split
# to split for every time series. This fixed amount of observations is currently set to the test length of the
# corresponding time series.

# In case this function is supposed to be used in the two-step case, data simply has to be filtered before hand
# to only contain positive demand observations.

def groupedTimeSeriesSplit(data, kFolds, testLength, groupFeature, timeFeature):
    
    # We reset the index because we have to access 'group.index' later on and
    # want to make sure that we return the implicit numerical indices for our splits.
    data = data.reset_index(drop = True)

    dataGrouped = data.groupby(groupFeature)
    splitNumbers = np.flip(np.array(range(kFolds)))
    
    foldsList = list()

    for i in splitNumbers:

        trainIndicesList = list()
        valIndicesList = list()

        valIndicesDict = dict()

        for name, group in dataGrouped:

            timeMin = int(group[timeFeature].min())
            timeMax = int(group[timeFeature].max())

            validationTimeMax = timeMax - i * testLength
            trainTimeMax = validationTimeMax - testLength

            trainTimesGroup = np.array(range(timeMin, trainTimeMax + 1))
            valTimesGroup = np.array(range(trainTimeMax + 1, validationTimeMax + 1))

            trainIndicesCheck = [timePoint in trainTimesGroup for timePoint in group[timeFeature]]
            valIndicesCheck = [timePoint in valTimesGroup for timePoint in group[timeFeature]]

            trainIndicesGroup = group.index[trainIndicesCheck]
            valIndicesGroup = group.index[valIndicesCheck]

            trainIndicesList.append(trainIndicesGroup)
            valIndicesList.append(valIndicesGroup)

        trainIndices = np.concatenate(trainIndicesList)
        valIndices = np.concatenate(valIndicesList)
        fold = (trainIndices, valIndices)

        foldsList.append(fold)

    return foldsList