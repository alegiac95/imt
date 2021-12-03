import logging.config
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pyls import pls_regression
from scipy.stats import zscore, spearmanr

with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    from netneurotools import freesurfer, stats

from .inputs import load_gene_expression, load_gene_labels, get_components
from .bootstrap import bootstrap_pls, bootstrap_genes, bootstrap_correlation

cfg_file_path = Path(__file__).parent / "log_config.yaml"
with open(cfg_file_path, "r") as config_file:
    log_cfg = yaml.safe_load(config_file.read())

logging.config.dictConfig(log_cfg)
logger = logging.getLogger("transcriptomics")
logger.setLevel(logging.DEBUG)


class ImagingTranscriptomics:
    def __init__(self, scan_data, **kwargs):
        """Initialise the imaging transcriptomics class with the input scan's data and number of components or variance
        explained.
        There are several settings that can be

        :param array-like scan_data: average values in the ROI defined by the Desikan-Killiany atlas.
        :param int n_components: number of components to use for the PLS regression.
        :param int variance: total explained variance by the PLS components.
        """
        logger.debug("Initializing ImagingTranscriptomics class.")
        self._method = kwargs.get("method") if kwargs.get("method") else "pls"
        self._regions = kwargs.get("reg") if kwargs.get("reg") else "cort+sub"
        self.scan_data = self.check_input_length(scan_data, self._regions)
        self.zscore_data = zscore(scan_data, ddof=1, axis=0)
        self.n_components = self.check_in_components(kwargs.get("n_components"))
        self.var = self.check_in_var(kwargs.get("variance"))
        if self._method == "pls":
            self.check_var_or_comp(self.var, self.n_components)
        self._cortical, self._subcortical = self.assign_regions(
            self.zscore_data)
        self._gene_expression = load_gene_expression(self._regions)
        self._gene_labels = load_gene_labels()
        # Initialise with defaults for later
        self.permuted = None
        self.r_boot = None
        self.p_boot = None
        self.gene_results = None
        self.var_components = None
        logger.debug("ImagingTranscriptomics class successfully initialized.")

    @staticmethod
    def check_input_length(data, regions):
        """Check that the length of the data given as input is correct in length (41).

        :param data: array to check has the correct length.
        :param regions: regions to use for the analysis can be either
        "cort", "sub" or "cort+sub".
        :raises AttributeError: if the length of the data is not 41.
        :return: data if it has correct length.
        """
        _cort_legth = 34
        _sub_length = 7
        _full_length = _cort_legth + _sub_length
        if regions == "cort":
            if len(data) == _cort_legth or len(data) == _full_length:
                return data
            else:
                raise AttributeError(
                    f"The length of the data given as input must be {_cort_legth}."
                )
        elif regions == "sub":
            if len(data) == _sub_length or len(data) == _full_length:
                return data
            else:
                raise AttributeError(
                    f"The length of the data given as input must be {_sub_length}."
                )
        elif regions == "cort+sub":
            if len(data) == _full_length:
                return data
            else:
                raise AttributeError(
                    f"The length of the data given as input must be {_full_length}."
                )

    @staticmethod
    def check_in_var(variance):
        """Check if the variance given as input is in the correct range.

        The variance can be in the range 0-100. If the variance is greater than
        1 the value is divided by 100.
        If the variance is None it will be kept as is.

        :param variance: input variance to check.
        :raises ValueError: if below 0 ir greater than 100.
        :return: variance if correct.
        """
        if variance is None:
            return variance
        elif 0.0 <= variance <= 1.0:
            return variance
        elif 1.0 < variance < 100:
            logger.warning(
                "The variance inputted was in the range 1-100. "
                "It has been converted to the range 0.0-1.0"
            )
            return variance / 100
        elif variance < 0.0:
            raise ValueError("The input variance cannot be negative!")
        elif variance > 100:
            raise ValueError("The input variance is too big!")
        elif isinstance(variance, str):
            raise TypeError("Strings are not supported, "
                            "please input a numeric value!")

    @staticmethod
    def check_in_components(components):
        """Check if the number of components given as input is in the range 1-15

        :param components: number of components given as input.
        :raises ValueError: if the component is not in the range 1-15 or None.
        :return: the number of components if correct.
        """
        if components is None:
            return components
        elif 1 <= components <= 15:
            return components
        else:
            raise ValueError("The number of components MUST be "
                             "in the range 1-15.")

    @staticmethod
    def check_var_or_comp(variance, components):
        if variance is None and components is None:
            raise AttributeError(
                "You must set either the variance or the number of components!"
            )

    @staticmethod
    def assign_regions(data):
        """Assign the regions to the data.

        :param data: data to assign the regions to.
        :return: data with the regions assigned.
        """
        if len(data) == 41:
            cort_data = data[0:34]
            sub_data = data[34:41]
        elif len(data) == 7:
            cort_data = None
            sub_data = data
        elif len(data) == 34:
            cort_data = data
            sub_data = None
        else:
            raise AttributeError(
                "The length of the data given as input must be either 41, 34 "
                "or 7."
            )
        return cort_data, sub_data

    def permute_data(self, iterations=1_000):  # done in new base
        """Permute the scan data for the analysis.

        The permutations are computed into cortical and subcortical regions separately and then merged. This is done
        to maintain the spatial autocorrelation in the cortical regions for more accuracy.
        To compute the cortical permutations the library python package ``netneurotools`` developed by R. Markello is
        used. For more information about the methods used you can refer to the official `documentation of the
        package. <https://netneurotools.readthedocs.io/en/latest/>_`

        :param int iterations: number of iterations to perform in the permutations.
        """
        self.permuted = np.zeros((self.zscore_data.shape[0], iterations))
        # subcortical
        logger.debug("Starting permutations.")
        if self._regions == "cort+sub":
            sub_permuted = np.array(
                [np.random.permutation(self._subcortical) for _ in range(iterations)]
            ).reshape(7, iterations)
            self.permuted[34:, :] = sub_permuted
        # Cortical
        # Annotation file for the Desikan-Killiany atlas in fs5
        annot_lh = Path(__file__).resolve().parent / "data/fsa5_lh_aparc.annot"
        annot_rh = Path(__file__).resolve().parent / "data/fsa5_rh_aparc.annot"
        # Get the parcel centroids of the Desikan-Killiany atlas
        parcel_centroids, parcel_hemi = freesurfer.find_parcel_centroids(
            lhannot=annot_lh,
            rhannot=annot_rh,
            version="fsaverage5",
            surf="sphere",
            method="surface",
        )
        # Mask the results to have only the left hemisphere
        left_hemi_mask = parcel_hemi == 0
        parcel_centroids, parcel_hemi = (
            parcel_centroids[left_hemi_mask],
            parcel_hemi[left_hemi_mask],
        )
        # Get the spin samples
        spins = stats.gen_spinsamples(
            parcel_centroids, parcel_hemi, n_rotate=iterations, method="vasa", seed=1234
        )
        cort_permuted = np.array(self._cortical[spins]).reshape(34, iterations)
        self.permuted[0:34, :] = cort_permuted
        logger.debug("End permutations.")

    def save_permutations(self, path):
        """Save the permutations to a csv file at a specified path.

        :param path: Path used to save the permutations, this *should* also
        include the name of the file, e.g., "~/Documents/my_permuted.csv"
        """
        if self.permuted is None:
            raise AttributeError(
                "There are no permutations of the scan available to save."
                "Before saving the permutations you need to compute them."
            )
        logger.info("Saving permutations to file %s", path)
        pd.DataFrame(self.permuted).to_csv(Path(path), header=None, index=False)

    def correlation(self):  # done in new base
        """Calculate the correlation between the imaging and genetic data.

        :return corr_genes: pearson correlation coefficient ordered in
        descending order.
        :return corr_gene_labels: labels of the genes ordered by correlation
        coefficient.
        """
        corr_ = np.zeros(self._gene_expression.shape[1])
        p_val = np.zeros(self._gene_expression.shape[1])
        for gene in range(15633):
            corr_[gene], p_val[gene] = spearmanr(
                self.zscore_data, self._gene_expression[:, gene]
            )
        corr_genes = np.sort(corr_)
        corr_gene_labels = self._gene_labels[np.argsort(corr_)]
        return corr_genes, corr_gene_labels

    def pls_all_components(self):  # done in new base
        """Compute a PLS regression with all components.

        After the regression is estimated, either the number of components or
        the estimated percentage of variance given by the components is
        estimated, depending on what is set by the user in the __init__()
        method.
        """
        logger.debug("Performing PLS with all 15 components.")
        results = pls_regression(
            self._gene_expression,
            self.zscore_data.reshape(41, 1),
            n_components=15,
            n_perm=0,
            n_boot=0,
        )
        var_exp = results.get("varexp")
        if self.n_components is None and self.var != 0.0:
            self.n_components = get_components(self.var, var_exp)
            logger.debug("Number of components has been set to: %s", self.n_components)
        elif self.var is None and self.n_components != 0:
            self.var = np.cumsum(var_exp)[self.n_components - 1]
            logger.debug(
                "Variance has been set to: %s", self.var
            )  # add number of variance set
        self.var_components = var_exp

    def run(self, n_iter=1_000, method=None):
        """Run the analysis of the imaging scan.

        :param int n_iter: number of permutations to make.
        :param str method: method to run the analysis, can be either "pls"
        for pls regression or "corr" cor simple correlation analysis.
        """
        logger.info("Starting imaging transcriptomics analysis.")
        if method is None:
            if self._method is None:
                raise AttributeError(
                    "You need to specify a method to run the analysis.")
            else:
                method = self._method
        if method is "pls":
            logger.info("Running analysis with PLS regression")
            self.pls_all_components()
            self.permute_data(iterations=n_iter)
            self.r_boot, self.p_boot = bootstrap_pls(
                self._gene_expression,
                self.zscore_data.reshape(41, 1),
                self.permuted,
                self.n_components,
                iterations=n_iter,
            )
            self.gene_results = bootstrap_genes(
                self._gene_expression,
                self.zscore_data.reshape(41, 1),
                self.n_components,
                self.scan_data,
                self._gene_labels,
                n_iter,
            )
            self.gene_results.boot_results.compute_values(
                self.n_components,
                self.gene_results.original_results.pls_weights,
                self.gene_results.original_results.pls_gene,
            )
        elif method is "corr":
            logger.info("Running analysis with correlation.")
            # run first analysis
            self.permute_data(iterations=n_iter)
            # bootstrap analysis
            self.gene_results = bootstrap_correlation(
                self.zscore_data,
                self._gene_expression,
                self.permuted,
                self._gene_labels,
            )
            self.gene_results.boot_results.compute_correlation(
                self.gene_results.original_results.pls_weights,
                self.gene_results.original_results.pls_gene,
                self.gene_results.original_results.gene_id,
            )
        else:
            raise NotImplementedError(
                f"The method {method} does not exist. "
                f"Please choose either pls or corr as "
                f"method to run the analysis."
            )
        logger.info("Running GSEA analysis.")
        # run GSEA analysis
        logger.info("Imaging transcriptomics analysis completed.")
