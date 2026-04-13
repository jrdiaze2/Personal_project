# Test Repository - cx-switch-automation

## Introduction
The cx-switch-automation repository contains tests and libraries specific for testing the CNX cx-switch services.  This is designed to run in the in the Roseville RTL envirnoment for testing along with running in the advanced project test phases in the cloud.

## OS Support / Tested
* [Ubuntu 22.04] - Roseville development workstation environment

### Pre-requisites

* Docker version 28.4.0 or above
* Docker Compose version of 2.39.2 or above

If your docker versions do not meet the requirements of the above on your Halon workstation, please contact SiS via help@labsupport.rose.rdlabs.hpecorp.net to request the team install the current versions of Docker and Docker compose to your halon workstation.
                     
## Repository layout
The repository layout is important to understand when building tests and libraries.  Please adhere to the guidelines set forth in the README for each specific area.

* cx-switch-test - service tests and libraries section
    * libraries - Here is where common library code along with service specific libraries should reside.
    * tests - This is where the tests directories along with the base test infrastructure (conftest.py) and requirements reside.
* services - docker compose files
    * The folder structure in this directory should be reflected accurately in the docker-compose-linux.yml in the top directory.  Under each of the folders here there are Dockerfiles to build the various levels of the runtime test environment.
* tools - Directory of toolsets to help drive the test runtime environment.


## Runtime Test Environment Organization
The runtime is built in conjunction with docker compose and some driver scripts in tools.  There are 2 layers to the development test runtime environment.
* Base OS container - Ubuntu based container with base toolsets to support testing
    * This container is built/maintained by the automation infra team
    * Two containers will be dropped into you docker image repository.
        * central-cnx/cnx-runtime-base:latest - OS base
        * cx-switch-env-local:latest - Library base
    * A cx-switch-env-local.tar.gz image archive will be saved in your repository root.
  
* Library layer container - This area really specific for the libraries in the environment.
    * The library layer sits on top of the Base OS container layer.
    * If any libraries are added or updated in the cx-switch-test/libraries area, we should always rebuild this layer of the 
    * To rebuild this layer without updating the base, simple run...
    ```sh
    # ./tools/build_local_run_env.sh --rebuild-libs
    ```
    * The cx-switch-env-local:latest is replaced in your local docker images repository
    * A new cx-switch-env-local.tar.gz image archive is generated and saved in your repository root.

## Running Tests via HT Launch - Roseville Environment Only
When working with topologies in the Roseville Environment (devices from the RTL), you will launch with ht.  Tests can be launched in an unattended fashion or against a reservation.
When running with ht the names of tests will be without the test_ prefix and without the .py suffix.  For example if I want to run test_kafka_mock_service.py the name would be kafka_mock_service.
* Running against a PMG reservation --h <central-lite> -t <test> -rsvnId <reservation #> 
    * Key Parameters - -h <central-lite> -t <test> -rsvnId <reservation #> -dockerEnvRebuild (rebuild lib layer) -centralLiteInst <cl.json>
    * Example: % ht -t kafka_mock_service -h central-lite -rsvnId 12345689 -dockerEnvRebuild -centralLiteInst <cl.json>
    * You do not need to do -dockerEnvRebuild all the time.  This will build a cx-switch-env-local.tar.gz in your local repo
* Running against a cluster in PMG:  -h central-cluster -t <test> -rsvnId <reservation #>
    * key paramter for a cluster is making sure -h central-cluster is set
* Running unattended against a central-lite
    * Key Parameters - -h central-lite-254gvt -t <test> 
    * This will queue up the test to run against a CL in the pool
* Running unattended against a central-cluster-gvt
    * Key Parameters - -h central-cluster-gvt -t <test>
    * This will queue up the test to run against a cluster scheduling instance in the pool
* Running unattended against the brooke cluster
    * Key Parameters - -h central-cluster-brooke -t <test>
    * This will queue up the test to run against the app-brooke cluster scheduling instance in the pool
* Running unattended against gvtdev01 cluster
    * Key Parameters - -h central-cluster-gvtdev01 -t <test>
    * This will queue up the test to run against the app-gvtdev01 cluster scheduling instance in the pool


## Running Tests via in No Topo Mode
If your test case does not have switches or does not need to interact with anything in the topology via CLI, then you can use
a new mode to launch call "No Topo Mode".  An example test case for this is in cx-switch-test/tests/infra_tests/test_notopo_example.py
This runmode can be used for test that only use core libraries to interact with Central or Gravity like graphql.  To launch
your test in the mode, make sure you have built the envionment as stated above.  Then you can run the following...
    ```sh
    # ./tools/cnx_run_notopo.sh --tests infra_tests/test_notopo_example.py --common_input ./common_input.json
    ```
* Here the --tests argument would be the list of tests from the cx-switch-tests/tests directory.  If running multiple tests, "," seperate the names
* The common_input.json would be an already formed common_input.json that was developed either against a CL or Cluster
* Logs for the run will be located in the repo_root directory under runtime_logs/<datestamp>

This mode is currently under development.  Look back for any changes or updates.

## Running Tests via in TopoPhysical Mode
If your test case has switches and you have a static topology or have a reservation in the automation pool, you can run you test case in topo-physical mode.  This is the mode we do run the framework in when running SMOKE & PLV testing.  The key parameters for topo-physical mode are...

Then you can run the following...
    ```sh
    # ./tools/cnx_run_topophys.sh --tests system_tests/graphql/properties_card/test_st_Gravity_UI_properties_standalone.py  --common_input ./common_input.json
    ```
* Here the --tests argument would be the list of tests from the cx-switch-tests/tests directory.  If running multiple tests, "," seperate the names
* The common_input.json would be an already formed common_input.json that was developed either against a CL or Cluster
* Logs for the run will be located in the repo_root directory under runtime_logs/<datestamp>


## VSF stack Fixture
Tests can now use a VSF stack fixture(vsf_stack_bringup) that will form a VSF stack of 2 or more nodes from standalone AOS-CX switches that support VSF stacking. 
The VSF fixture is also called as part of the onboarding fixture and once the stack is formed, the node designated as conductor node from VSF is onboarded. 
It is important to note that the standby and member nodes of the VSF stack are not onboarded, but these nodes are availabe to the test to perform 
certain limited operations.

Stack formation happens automatically if the test topology defines a node with 'auto_vsf_role' and 'auto_vsf_stack'. Valid values for auto_vsf_role are 'conductor', 'standby' or 'member'. 
The fixture also supports creation of multiple stacks by specifying 'auto_vsf_stack' that defines which stack a node belongs to.
In the below example, sw1 and sw2 are part of 'stack_1' and sw3 and sw4 are part of 'stack_2'.

Example:

    ```sh
    [type=halon_0 name="sw1" auto_vsf_role="conductor" auto_vsf_stack="stack_1" topo_filters="devIdCertificate:present,system-family:6300F,system-family:6300M,system-family:6200F,system-family:6200M"] sw1
    [type=halon_0 name="sw2" auto_vsf_role="standby" auto_vsf_stack="stack_1" topo_filters="devIdCertificate:present,system-family:6300F,system-family:6300M,system-family:6200F,system-family:6200M"] sw2
    [type=halon_0 name="sw3" auto_vsf_role="conductor" auto_vsf_stack="stack_2" topo_filters="devIdCertificate:present,system-family:6300F,system-family:6300M,system-family:6200F,system-family:6200M"] sw3
    [type=halon_0 name="sw4" auto_vsf_role="standby" auto_vsf_stack="stack_2" topo_filters="devIdCertificate:present,system-family:6300F,system-family:6300M,system-family:6200F,system-family:6200M"] sw4
    ```

More example .py files for tests are located in cx-switch-test/tests/infra_tests/
