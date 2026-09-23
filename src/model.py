"""
Phase 4 count model: which structural conditions go with higher overdose rates?

Model: negative binomial regression of tract overdose deaths (2015-2025), with
log(population x years) as an offset so the coefficients describe *rates*.
Results are reported as incidence rate ratios (IRRs): an IRR of 1.20 for
"households without a vehicle, per 10 points" means a tract with 10 more
percentage points of car-free households has a 20% higher overdose rate,
holding the other variables fixed.

This is descriptive, not causal. See methodology D6 for why need-based access
is left out of the model (it has deaths in its denominator).
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from src.config import ANALYSIS_END_YEAR, ANALYSIS_START_YEAR, MIN_POPULATION_FOR_RATE

# Percent variables are divided by 10 so each IRR reads "per 10 percentage points",
# which is a more meaningful step than 1 point for tract-level percentages
PERCENT_PREDICTORS = {
    "pct_poverty": "Residents below poverty",
    "pct_no_vehicle": "Households without a vehicle",
    "pct_uninsured": "Residents uninsured",
    "pct_nh_black": "Black residents",
    "pct_hispanic": "Hispanic residents",
}
OTHER_PREDICTORS = {
    "access_moud_per_100k_pop": "MOUD sites in reach per 100k residents",
}


def prepare_model_data(tract_table):
    """
    Keep tracts with enough residents and complete ACS data, and add model columns.

    Returns
    -------
    pd.DataFrame
        One row per usable tract with scaled predictors and a `log_exposure` offset.
    """
    needed = list(PERCENT_PREDICTORS) + list(OTHER_PREDICTORS)
    data = tract_table[tract_table["population_2020"] >= MIN_POPULATION_FOR_RATE]
    data = data.dropna(subset=needed).copy()

    years = ANALYSIS_END_YEAR - ANALYSIS_START_YEAR + 1
    # Offset: expected deaths scale with person-years, so log(population x years)
    # enters the model with its coefficient fixed at 1
    data["log_exposure"] = np.log(data["population_2020"] * years)

    for column in PERCENT_PREDICTORS:
        data[f"{column}_per10"] = data[column] / 10

    # The first two digits of a Cook County tract code group neighboring tracts
    # (in Chicago they line up with community areas), which we use as clusters
    data["cluster"] = data["GEOID"].str[5:7]
    return data.reset_index(drop=True)


def model_formula():
    """Build the regression formula from the predictor lists."""
    terms = [f"{column}_per10" for column in PERCENT_PREDICTORS] + list(OTHER_PREDICTORS)
    return "overdose_deaths ~ " + " + ".join(terms)


def fit_poisson(data):
    """Fit the Poisson baseline and return it with its dispersion ratio."""
    poisson = smf.glm(model_formula(), data, family=sm.families.Poisson(),
                      offset=data["log_exposure"]).fit()
    # Poisson assumes variance = mean, so this ratio should be near 1. Far
    # above 1 means overdispersion, and Poisson standard errors are too small.
    dispersion = poisson.pearson_chi2 / poisson.df_resid
    return poisson, dispersion


def fit_negative_binomial(data, formula=None):
    """
    Fit the negative binomial model with cluster-robust standard errors.

    `formula` defaults to the main model; pass a different one to test
    added variables with the exact same fitting steps.

    Two steps: estimate the dispersion parameter (alpha) by maximum likelihood,
    then refit as a GLM with that alpha so we can use clustered standard
    errors. Clustering is needed because neighboring tracts have correlated
    residuals (see `morans_i`), which makes ordinary standard errors too small.

    Returns
    -------
    tuple
        (fitted GLM result with clustered SEs, estimated alpha)
    """
    formula = formula or model_formula()
    first_pass = smf.negativebinomial(formula, data, offset=data["log_exposure"]).fit(disp=0)
    alpha = first_pass.params["alpha"]

    cluster_ids = pd.factorize(data["cluster"])[0]
    model = smf.glm(formula, data, family=sm.families.NegativeBinomial(alpha=alpha),
                    offset=data["log_exposure"])
    result = model.fit(cov_type="cluster", cov_kwds={"groups": cluster_ids})
    return result, alpha


def morans_i(values, geometries, permutations=999, seed=42):
    """
    Moran's I for spatial autocorrelation, with a permutation p-value.

    Neighbors are tracts that share a border or a corner ("queen" contiguity).
    I near 0 means no spatial pattern; positive means similar values cluster.
    The p-value comes from shuffling the values across tracts many times and
    counting how often the shuffled I is at least as large as the real one.

    Parameters
    ----------
    values : array-like
        One value per tract (here, model residuals).
    geometries : gpd.GeoSeries
        Tract shapes, in the same order as `values`.
    """
    frame = geometries.to_frame("geometry").reset_index(drop=True)
    pairs = frame.sjoin(frame, predicate="touches")
    left, right = pairs.index.values, pairs["index_right"].values

    centered = np.asarray(values, dtype=float) - np.mean(values)
    n, links = len(centered), len(left)

    def statistic(z):
        return (n / links) * (z[left] * z[right]).sum() / (z ** 2).sum()

    observed = statistic(centered)
    rng = np.random.default_rng(seed)
    shuffled = np.array([statistic(rng.permutation(centered)) for _ in range(permutations)])
    p_value = (np.sum(shuffled >= observed) + 1) / (permutations + 1)
    return observed, p_value


def rate_ratio_table(result):
    """Turn model coefficients into a readable table of rate ratios with 95% CIs."""
    labels = {f"{column}_per10": f"{label} (per 10 pts)" for column, label in PERCENT_PREDICTORS.items()}
    labels.update(OTHER_PREDICTORS)

    confidence = result.conf_int()
    table = pd.DataFrame({
        "rate_ratio": np.exp(result.params),
        "ci_low": np.exp(confidence[0]),
        "ci_high": np.exp(confidence[1]),
        "p_value": result.pvalues,
    }).drop(index="Intercept")
    return table.rename(index=labels)
