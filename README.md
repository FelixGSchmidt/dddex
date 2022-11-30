dddex: Data-Driven Density Estimation x
================

<!-- WARNING: THIS FILE WAS AUTOGENERATED! DO NOT EDIT! -->

## Install

``` sh
pip install dddex
```

## What is dddex?

The package name `dddex` stands for *Data-Driven Density Estimaton x*.
New approaches are being implemented for estimating conditional
densities without any parametric assumption about the underlying
distribution. All those approaches take an arbitrary point forecaster as
input and turn them into a new object that outputs an estimation of the
conditional density based on the point predictions of the original point
forecaster. The *x* in the name emphasizes that the approaches can be
applied to any point forecaster. In this package several approaches are
being implementing via the following classes:

- [`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
- [`LevelSetKDEx_kNN`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex_knn)
- [`LevelSetKDEx_NN`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex_nn)
- [`LevelSetKDEx_multivariate`](https://kaiguender.github.io/dddex/levelsetkdex_multivariate.html#levelsetkdex_multivariate)

In the following we are going to work exclusively with the class
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
because the most important methods are all pretty much the same. All
models can be run easily with only a few lines of code and are designed
to be compatible with the well known *Scikit-Learn* framework.

## How to use: LevelSetKDEx

To ensure compatibility with Scikit-Learn, as usual the class
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
implements a `fit` and `predict` method. As the purposes of both classes
is to compute estimations of conditional densities, the `predict` method
outputs p-quantiles rather than point forecasts.

Our choice of the class-names is supposed to be indicative of the
underlying models: The name *LevelSet* stems from the fact that both
methods operate with the underlying assumption that the values of point
forecasts generated by the same point forecaster can be interpreted as a
similarity measure between samples. *KDE* is short for *Kernel Density
Estimator* and the *x* yet again signals that the classes can be
initialized with any point forecasting model.

In the following, we demonstrate how to use the class
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
to compute estimations of the conditional densities and quantiles for
the [Yaz Data
Set](https://opimwue.github.io/ddop/modules/auto_generated/ddop.datasets.load_yaz.html#ddop.datasets.load_yaz).
As explained above,
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
is always based on a point forecaster that is being specified by the
user. In our example we use the well known `LightGBMRegressor` as the
underlying point predictor.

``` python
from dddex.levelSetKDEx import LevelSetKDEx, LevelSetKDEx_kNN, LevelSetKDEx_NN
from dddex.levelSetKDEx_multivariate import LevelSetKDEx_multivariate

from dddex.loadData import loadDataYaz
from lightgbm import LGBMRegressor
```

``` python
dataYaz, XTrain, yTrain, XTest, yTest = loadDataYaz(testDays = 28, returnXY = True)
LGBM = LGBMRegressor(n_jobs = 1)
```

There are three parameters for
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex):

- **estimator**: A point forecasting model that must have a `predict`
  method.
- **binSize**: The amount of training samples considered to compute the
  conditional densities (for more details, see *To be written*).
- **weightsByDistance**: If *False*, all considered training samples are
  weighted equally. If *True*, training samples are weighted by the
  inverse of the distance of their respective point forecast to the
  point forecast of the test sample at hand.

``` python
LSKDEx = LevelSetKDEx(estimator = LGBM, 
                      binSize = 100,
                      weightsByDistance = False)
```

There is no need to run `fit` on the point forecasting model before
initializing *LevelSetKDEx*, because the `fit` method of
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
automatically checks whether the provided model has been fitted already
or not and runs the respective `fit` method of the point forecaster if
needed.

It should be noted, that running `fit` for the *LevelSetKDEx* approaches
takes exceptionally little time even for datasets with $>10^6$ samples
(provided, of course, that the underlying point forecasting model has
been fitted before hand).

``` python
LSKDEx.fit(X = XTrain, y = yTrain)
```

In order to compute conditional densities for test samples now, we
simply run the `getWeights` method.

``` python
conditionalDensities = LSKDEx.getWeights(X = XTest,
                                         outputType = 'summarized')

print(f"probabilities: {conditionalDensities[0][0]}")
print(f"demand values: {conditionalDensities[0][1]}")
```

    probabilities: [0.49 0.01 0.21 0.01 0.16 0.07 0.04 0.01]
    demand values: [0.         0.01075269 0.04       0.04878049 0.08       0.12
     0.16       0.2       ]

Here, `conditionalDensities` is a list whose elements correspond to the
samples specified via `X`. Every element contains a tuple, whose first
entry constitutes probabilities and the second entry corresponding
demand values (side note: The demand values have been scaled to lie in
$[0, 1]$). In the above example, we can for example see that our model
estimates that for the first test sample the demand will be 0 with a
probability of 49%.

Like the input argument *outputType* of `getWeights` suggests, we can
output the conditional density estimations in various different forms.
All in all, there are currently 5 output types specifying how the output
for each sample looks like:

- **all**: An array with the same length as the number of training
  samples. Each entry represents the probability of each training
  sample.
- **onlyPositiveWeights**: A tuple. The first element of the tuple
  represents the probabilities and the second one the indices of the
  corresponding training sample. Only probalities greater than zero are
  returned. Note: This is the most memory and computationally efficient
  output type.
- **summarized**: A tuple. The first element of the tuple represents the
  probabilities and the second one the corresponding value of `yTrain`.
  The probabilities corresponding to identical values of `yTrain` are
  aggregated.
- **cumulativeDistribution**: A tuple. The first element of the tuple
  represents the probabilities and the second one the corresponding
  value of `yTrain`.
- **cumulativeDistributionSummarized**: A tuple. The first element of
  the tuple represents the probabilities and the second one the
  corresponding value of `yTrain`. The probabilities corresponding to
  identical values of `yTrain` are aggregated.

For example, by setting
`outputType = 'cumulativeDistributionSummarized'` we can compute an
estimation of the conditional cumulative distribution function for each
sample. Below, we can see that our model predicts the demand of the
first sample to be lower or equal than 0.16 with a probability of 99%.

``` python
cumulativeDistributions = LSKDEx.getWeights(X = XTest,
                                            outputType = 'cumulativeDistributionSummarized')

print(f"cumulated probabilities: {cumulativeDistributions[0][0]}")
print(f"demand values: {cumulativeDistributions[0][1]}")
```

    cumulated probabilities: [0.49 0.5  0.71 0.72 0.88 0.95 0.99 1.  ]
    demand values: [0.         0.01075269 0.04       0.04878049 0.08       0.12
     0.16       0.2       ]

We can also compute estimations of quantiles using the `predict` method.
The parameter *probs* specifies the quantiles we want to predict.

``` python
predRes = LSKDEx.predict(X = XTest,
                         outputAsDf = True, 
                         probs = [0.1, 0.5, 0.75, 0.99])
print(predRes.iloc[0:6, :].to_markdown())
```

    |    |       0.1 |       0.5 |   0.75 |   0.99 |
    |---:|----------:|----------:|-------:|-------:|
    |  0 | 0         | 0.0107527 |   0.08 |   0.16 |
    |  1 | 0         | 0.08      |   0.12 |   0.2  |
    |  2 | 0.04      | 0.0967742 |   0.12 |   0.24 |
    |  3 | 0.056338  | 0.12      |   0.16 |   0.28 |
    |  4 | 0.04      | 0.0967742 |   0.12 |   0.24 |
    |  5 | 0.0666667 | 0.16      |   0.2  |   0.32 |

## How to tune binSize parameter of LevelSetKDEx

`dddex` also comes with the class
[`binSizeCV`](https://kaiguender.github.io/dddex/levelsetkdex.html#binsizecv)
that tunes the important *binSize* parameter via cross-validation in an
efficient manner. The class is designed in a very similar fashion to the
cross-validation classes of Scikit-Learn. As such, at first
[`binSizeCV`](https://kaiguender.github.io/dddex/levelsetkdex.html#binsizecv)is
initialized with all the settings for the cross-validation.

- **estimatorLSx**: Either an object of class
  [`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
  or
  [`LevelSetKDEx_kNN`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex_knn)
- **cvFolds**: An iterable yielding (train, test) splits as arrays of
  indices
- **binSizeGrid**: The candidate values of *binSize* to evaluate
- **probs**: The probabilities for which quantiles are computed and
  evaluated.
- **refitPerProb**: If True, for ever probability a fitted copy of
  *estimatorLSx* with the best binSize for the respective p-quantile is
  stored in the attribute *bestEstimatorLSx*. If False, only a single
  fitted copy of *estimatorLSx* is stored with the binSize that yielded
  the lowest average aggregated costs over all quantile estimations.
- **n_jobs**: How many cross-validation split results to compute in
  parallel.

After specifying the settings, `fit` has to be called to compute the
results of the cross validation. The performance of every *binSize*
candidate value is being evaluated by computing the relative reduction
of the pinball loss in comparison to the quantile estimations generated
by *SAA* (Sample Average Approximation) for every quantile.

``` python
from dddex.levelSetKDEx import binSizeCV
from dddex.utils import groupedTimeSeriesSplit

dataTrain = dataYaz[dataYaz['label'] == 'train']
cvFolds = groupedTimeSeriesSplit(data = dataTrain, 
                                 kFolds = 3,
                                 testLength = 28,
                                 groupFeature = 'id',
                                 timeFeature = 'dayIndex')

LSKDEx = LevelSetKDEx(estimator = LGBM,
                      binSize = None,
                      weightsByDistance = False)

CV = binSizeCV(estimatorLSx = LSKDEx,
               cvFolds = cvFolds,
               binSizeGrid = [20, 100, 400, 1000],
               probs = [0.01, 0.25, 0.5, 0.75, 0.99],
               refitPerProb = True,
               n_jobs = 3)

CV.fit(X = XTrain, y = yTrain)
```

The best value for *binSize* can either be computed for every quantile
separately or for all quantiles at once by computing the average cost
reduction over all quantiles.

``` python
print(f"Best binSize over all quantiles: {CV.bestBinSize}")
CV.bestBinSize_perProb
```

    Best binSize over all quantiles: 1000

    0.01    1000
    0.25      20
    0.50     100
    0.75     100
    0.99    1000
    dtype: int64

The exact results are also stored as attributes. The easiest way to view
the results is given via `cv_results`, which depicts the average results
over all cross-validation folds:

``` python
print(CV.cv_results.to_markdown())
```

    |      |    0.01 |     0.25 |      0.5 |     0.75 |    0.99 |
    |-----:|--------:|---------:|---------:|---------:|--------:|
    |   20 | 3.23956 | 0.849528 | 0.808262 | 0.854069 | 2.46195 |
    |  100 | 1.65191 | 0.857026 | 0.803632 | 0.835323 | 1.81003 |
    |  400 | 1.64183 | 0.860281 | 0.812806 | 0.837641 | 1.57534 |
    | 1000 | 1.54641 | 0.869606 | 0.854369 | 0.88065  | 1.52644 |

The attentive reader will certainly notice that values greater than 1
imply that the respective model performed worse than SAA. This is, of
course, simply due to the fact, that we didn’t tune the hyperparameters
of the underlying `LGBMRegressor` point predictor and instead used the
default parameter values. The
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)classes
are able to produce highly accurate density estimations, but are
obviously not able to turn a terrible point predictor into a highly
performant conditional density estimator. The performance of the
underlying point predictor and the constructed
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
model go hand in hand.

We can also access the results for every fold separately via
`cv_results_raw`, which is a list with one entry per fold:

``` python
CV.cv_results_raw
```

    [          0.01      0.25      0.50      0.75      0.99
     20    3.068598  0.854633  0.855041  0.953362  3.663885
     100   1.626054  0.871327  0.833379  0.907911  2.591117
     400   1.732673  0.860440  0.828015  0.890643  2.190292
     1000  1.464534  0.873277  0.858563  0.891858  1.830334,
               0.01      0.25      0.50      0.75      0.99
     20    4.157297  0.841141  0.795929  0.830544  1.883320
     100   1.752709  0.862970  0.812126  0.819613  1.416013
     400   2.085622  0.887758  0.839370  0.859290  1.296445
     1000  1.767468  0.869484  0.860893  0.876293  1.464460,
               0.01      0.25      0.50      0.75      0.99
     20    2.492787  0.852811  0.773815  0.778301  1.838642
     100   1.576956  0.836781  0.765390  0.778446  1.422947
     400   1.107203  0.832645  0.771034  0.762992  1.239275
     1000  1.407221  0.866058  0.843651  0.873799  1.284521]

The models with the best *binSize* parameter are automatically computed
while running `fit` and can be accessed via `bestEstimatorLSx`. If
`refitPerProb = True`, then `bestEstimatorLSx` is a dictionary whose
keys are the probabilities specified via the paramater *probs*.

``` python
LSKDEx_best99 = CV.bestEstimatorLSx[0.99]
predRes = LSKDEx_best99.predict(X = XTest,
                                probs = 0.99)
print(predRes.iloc[0:6, ].to_markdown())
```

    |    |   0.99 |
    |---:|-------:|
    |  0 |   0.32 |
    |  1 |   0.32 |
    |  2 |   0.32 |
    |  3 |   0.32 |
    |  4 |   0.32 |
    |  5 |   0.32 |

## Benchmarks: Random Forest wSAA

The `dddex` package also contains useful non-parametric benchmark models
to compare the performance of the
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
models to other state of the art non-parametric models capable of
generating conditional density estimations. In a [meta analysis
conducted by S. Butler et
al.](https://ml-eval.github.io/assets/pdf/ICLR22_Workshop_ML_Eval_DDNV.pdf)
the most performant model has been found to be [weighted sample average
approximation
(wSAA)](https://pubsonline.informs.org/doi/10.1287/mnsc.2018.3253) based
on *Random Forest*. This model has been implemented in a Scikit-Learn
fashion as well.

``` python
from dddex.wSAA import RandomForestWSAA
RF = RandomForestWSAA()
```

[`RandomForestWSAA`](https://kaiguender.github.io/dddex/wsaa.html#randomforestwsaa)
is a class derived from the original `RandomForestRegressor` class from
Scikit-Learn, that has been extended to be able to generate conditional
density estimations in the manner described by Bertsimas et al. in their
paper [*From Predictive to prescriptive
analytics*](https://pubsonline.informs.org/doi/10.1287/mnsc.2018.3253).
The *Random Forest* modell is being fitted in exactly the same way as
the original *RandomForestRegressor*:

``` python
RF.fit(X = XTrain, y = yTrain)
```

Identical to the
[`LevelSetKDEx`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex)
and
[`LevelSetKDEx_kNN`](https://kaiguender.github.io/dddex/levelsetkdex.html#levelsetkdex_knn)
classes, an identical method called `getWeights` and `predict`are
implemented to compute conditional density estimations and quantiles.
The output is the same as before.

``` python
conditionalDensities = RF.getWeights(X = XTest,
                                     outputType = 'summarized')

print(f"probabilities: {conditionalDensities[0][0]}")
print(f"demand values: {conditionalDensities[0][1]}")
```

    probabilities: [0.05339683 0.21071739 0.21882087 0.16315079 0.23533464 0.06696032
     0.03782118 0.00555556 0.00824242]
    demand values: [0.   0.04 0.08 0.12 0.16 0.2  0.24 0.28 0.32]

``` python
predRes = RF.predict(X = XTest,
                     probs = [0.01, 0.5, 0.99],
                     outputAsDf = True)
print(predRes.iloc[0:6, :].to_markdown())
```

    |    |   0.01 |   0.5 |   0.99 |
    |---:|-------:|------:|-------:|
    |  0 |   0    |  0.12 |   0.28 |
    |  1 |   0    |  0.12 |   0.36 |
    |  2 |   0.04 |  0.12 |   0.36 |
    |  3 |   0    |  0.16 |   0.32 |
    |  4 |   0    |  0.12 |   0.32 |
    |  5 |   0    |  0.2  |   0.32 |

The original `predict` method of the `RandomForestRegressor` has been
renamed to `pointPredict`:

``` python
RF.pointPredict(X = XTest)[0:6]
```

    array([0.106 , 0.1244, 0.14  , 0.1528, 0.132 , 0.1984])
