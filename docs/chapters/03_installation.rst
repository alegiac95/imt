.. _Installation:

============
Installation
============

To install the ``imaging-transcriptomics`` Python package you must first of all have Python ``v3.6+`` installed on your system along with the ``pip`` package manager.

.. warning::

    At current time Python versions 3.9+ are not fully supported as there
are some issue during the installation of the Numpy version used by the
toolbox in these versions of Python.


.. tip::

    We suggest installing the package in a dedicated python environment using `venv <https://docs.python.org/3/library/venv.html>`_ or `conda <https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html>`_ depending on your personal choice. The installation on a dedicated environment avoids the possible clashes of dependencies after or during installation.


.. note::

    All following steps assume that, if you have created a dedicated environment, this is currently active. If you are unsure you can check with ``which python`` from your terminal or activate your environment via the ``source activate`` (for conda managed environments) or ``source venv/bin/activate`` (for venv managed environments).

Before installing the ``imaging-transcriptomics`` package we need to install a package that is not available through PyPi but from GitHub only.
This package is `pypls <https://github.com/netneurolab/pypyls>`_ and is used in the script to perform all PLS regressions.
In order to install it you can run the following command from your terminal

.. code:: shell

    pip install -e git+https://github.com/netneurolab/pypyls.git/#egg=pyls

This will install install the GitHub repository directly using pip and it will make it available with the name ``pyls``.

.. warning::

    Do not install pyls directly from pip with the command ``pip install pyls`` as this is a completely different package!

A second package to install for the full functionalities of the imaging-transcriptomics toolbox is the `ENIGMA toolbox <https://enigma-toolbox.readthedocs.io/en/latest/index.html>`_ . 
To install this we'll follow the instructions of the developers. In brief, install this by running the commands:

.. code:: shell

    git clone https://github.com/MICA-MNI/ENIGMA.git
    cd ENIGMA
    python setup.py install

Once these packages is installed you can install the ``imaging-transcriptomics`` package by running:

.. code::

    pip install imaging-transcriptomics


Once you get the message that the installation has completed you are set to go!

.. note:: The version ``v1.0.0`` and ``v1.0.1``, can cause some issues on the installation due to compatibility issues of some packages. In version ``v1.0.2+`` this issue has been resolved during installation. If you have one of the older versions installed you might want to update the version using the command ``pip install --upgrade imaging-transcriptomics``. 

.. note:: From version ``v1.1.0`` has the possibility of running directly from the toolbox also the gene set enrichment analysis (GSEA). Version ``v1.1.8`` has a major speedup in the correlation analyses, reducing the overall time needed to run the analysis.
