asimov-lalinference
====================

``asimov-lalinference`` is a plugin for `Asimov <https://asimov.docs.ligo.org/asimov/>`_ 0.7+
that integrates the `LALInference <https://lscsoft.docs.ligo.org/lalsuite/lalinference/>`_
parameter-estimation pipeline. Once installed, the plugin is discovered automatically via
Asimov's entry-point registry — no extra configuration is required.

.. warning::

   LALInference has been superseded by newer sampling pipelines (bilby, RIFT) and its
   integration with Asimov is not fully reviewed. It **must not** be used for
   collaboration parameter estimation analyses. It remains useful for cross-checks and
   for replicating older analyses.

**What it does**

* Builds a ``lalinference_pipe`` DAG from a production's ``.ini`` file (either pre-seeded
  in the event repository, or rendered by Asimov from this plugin's bundled
  :attr:`config_template <asimov_lalinference.lalinference.LALInference.config_template>`
  using the production's meta-data — waveform, data, likelihood, priors).
* Submits the resulting DAG to an HTCondor or Slurm scheduler via Asimov's
  scheduler-agnostic API.
* Once the run completes (a real ``posterior_samples/posterior_*.hdf5`` file is produced),
  hands off to the `asimov-pesummary <https://github.com/transientlunatic/asimov-pesummary>`_
  plugin for post-processing, if it is installed.

Installation
------------

LALInference itself is only distributed via conda-forge — there is no PyPI wheel — so
this plugin has two installation steps:

.. code-block:: bash

   conda install -c conda-forge lalinference
   pip install asimov-lalinference

From source:

.. code-block:: bash

   conda install -c conda-forge lalinference
   git clone https://github.com/transientlunatic/asimov-lalinference.git
   cd asimov-lalinference
   pip install -e ".[docs,test]"

Configuration
-------------

A minimal production blueprint:

.. code-block:: yaml

   kind: analysis
   name: Prod0
   pipeline: lalinference
   status: ready
   interferometers:
     - H1
     - L1
   engine: lalinferencenest
   nparallel: 4
   waveform:
     approximant: IMRPhenomPv2pseudoFourPN
     reference frequency: 20
   data:
     segment length: 4
     channels:
       H1: H1:DCS-CALIB_STRAIN_CLEAN_C01
       L1: L1:DCS-CALIB_STRAIN_CLEAN_C01
     frame types:
       H1: H1_HOFT_C01
       L1: L1_HOFT_C01
   likelihood:
     sample rate: 2048
     minimum frequency:
       H1: 20
       L1: 20
   priors:
     mass 1:
       minimum: 1
       maximum: 200
     mass ratio:
       minimum: 0.05
       maximum: 1.0
     luminosity distance:
       minimum: 10
       maximum: 5000
   scheduler:
     accounting group: ligo.dev.o4.cbc.pe.lalinference

The ``sampler`` block controls the nested-sampling settings that were historically
hard-coded in the template (``nlive``, ``tolerance``, ``maxmcmc``, ``neff``, ``ntemps``);
all default to their original values if omitted:

.. code-block:: yaml

   sampler:
     nlive: 2048
     tolerance: 0.1

Alternatively, a production's ``.ini`` can be committed directly to the event repository
(at ``<category>/<production name>.ini``, ``analyses/`` by default) instead of relying on
templated generation — Asimov's ``manage build`` step only renders one if it doesn't
already find one. This is how this plugin's own end-to-end test is set up, using
LALInference's built-in simulated ("fake-cache") Gaussian noise rather than real strain
data.

Status messages
~~~~~~~~~~~~~~~~

``wait``
   The pipeline will ignore the production.

``ready``
   Asimov will attempt to submit the job to the scheduler.

``running``
   Applied after the job is submitted to the cluster.

``stuck``
   Applied when the job is held or an error is detected in the pipeline's execution.

``finished``
   Applied when normal termination of the pipeline is detected (a real
   ``posterior_samples/posterior_*.hdf5`` file exists).

Post-processing
----------------

Once a job completes, ``after_completion()`` looks up the ``pesummary`` pipeline via the
``asimov.pipelines`` entry-point group and hands the production off to it. If
``asimov-pesummary`` is not installed, a clear ``PipelineException`` is raised (rather
than silently failing) explaining how to install it:

.. code-block:: bash

   pip install asimov-pesummary

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api
