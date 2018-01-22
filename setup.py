from setuptools import setup, find_packages

setup(
    name='sheepdog',
    version='0.2.0',
    description='Flask blueprint for herding data submissions',
    url='https://github.com/uc-cdis/sheepdog',
    license='Apache',
    packages=find_packages(),
    install_requires=[
        'boto==2.36.0',
        'psycopg2>=2.7.3',
        'cryptography==2.1.2',
        'Flask-Cors==1.9.0',
        'Flask-SQLAlchemy-Session==1.1',
        'Flask==0.10.1',
        'fuzzywuzzy==0.6.1',
        'graphene==0.10.2',
        'jsonschema==2.5.1',
        'lxml==3.8.0',
        'PyYAML==3.11',
        'requests==2.7',
        'setuptools==30.1.0',
        'datamodelutils',
        'dictionaryutils',
        'gdcdatamodel',
        'gdcdictionary',
        'indexclient',
        'signpostclient',
        'psqlgraph',
        'userdatamodel',
    ],
    dependency_links=[
        'git+https://git@github.com/uc-cdis/userdatamodel.git@cb7143c709a1173c84de4577d3e866318a2cc834#egg=userdatamodel',
        'git+https://git@github.com/uc-cdis/cdis_oauth2client.git@0.1.2#egg=cdis_oauth2client',
        'git+https://git@github.com/NCI-GDC/psqlgraph.git@1.2.0#egg=psqlgraph',
        'git+https://git@github.com/uc-cdis/cdiserrors.git@0.0.4#egg=cdiserrors',
        'git+https://git@github.com/uc-cdis/cdis-python-utils.git@0.2.2#egg=cdispyutils',
        'git+https://git@github.com/uc-cdis/dictionaryutils.git@1.1.0#egg=dictionaryutils',
        'git+https://git@github.com/uc-cdis/datamodelutils.git@0.2.0#egg=datamodelutils',
        'git+https://git@github.com/uc-cdis/authutils.git@feat/api-373-separate-authutils#egg=authutils',
        'git+https://git@github.com/uc-cdis/indexclient.git@d49134f4626b69a8ef02c189ed0047ad1a635cb0#egg=indexclient',
        'git+https://git@github.com/NCI-GDC/gdcdatamodel.git@1.1.0#egg=gdcdatamodel',
        'git+https://git@github.com/uc-cdis/datadictionary.git@0.1.1#egg=gdcdictionary',
        'git+https://git@github.com/NCI-GDC/cdisutils.git@4a75cc05c7ba2174e70cca9c9ea7e93947f7a868#egg=cdisutils',
        'git+https://git@github.com/NCI-GDC/python-signpostclient.git@ca686f55772e9a7f839b4506090e7d2bb0de5f15#egg=signpostclient',
    ],
)
