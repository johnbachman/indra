from __future__ import absolute_import, print_function, unicode_literals
from builtins import dict, str
from os.path import abspath, join, dirname, isfile
import yaml
from nose.tools import raises
from indra.statements import Complex, ActiveForm
from indra.tools.nl_builder import NlBuilder, NlModule, NlSentence

test_data_dir = join(dirname(abspath(__file__)), 'nl_builder_test_data')

def test_constructor():
    nlb = NlBuilder([])
    assert nlb.cache_dir == '_cache'
    assert nlb.sentence_stmts == {}


def test_load_yaml():
    filename = join(test_data_dir, 'apoptosis.yaml')
    nlb = NlBuilder([filename])
    assert nlb._yaml_files == [join(test_data_dir, 'apoptosis.yaml')]


@raises(ValueError)
def test_invalid_yaml():
    nlb = NlBuilder(5)


def test_load_module():
    yaml_file = join(test_data_dir, 'apoptosis.yaml')
    with open(yaml_file, 'rt') as f:
        yaml_dict = yaml.load(f)
    nlm = NlModule(yaml_dict)
    assert len(nlm.submodules) == 1
    submod = nlm.submodules[0]
    assert isinstance(submod, NlModule)
    assert submod.description == None
    assert submod.units == None
    assert len(submod.sentences) == 5
    assert isinstance(submod.sentences[0], NlSentence)


@raises(ValueError)
def test_both_sent_and_submod():
    """A module YAML file should not contain both sentences and submodules."""
    filename = join(test_data_dir, 'sentences_and_submodules.yaml')
    nlb = NlBuilder(filename)


@raises(ValueError)
def test_neither_sent_nor_submod():
    """A module YAML file must contain either sentences or submodules."""
    filename = join(test_data_dir, 'no_sentences_or_submodules.yaml')
    nlb = NlBuilder(filename)


def test_multiple_submodules():
    filename = join(test_data_dir, 'multiple_submodules.yaml')
    nlb = NlBuilder(filename)
    assert len(nlb.modules) == 1
    submods = nlb.modules[0].submodules
    assert len(submods) == 2
    assert len(submods[0].sentences) == 3
    assert len(submods[1].sentences) == 4


def test_all_sentences():
    filename = join(test_data_dir, 'multiple_submodules.yaml')
    nlb = NlBuilder(filename)
    sentences = nlb.all_sentences()
    assert len(sentences) == 7


def test_process_text():
    filename = join(test_data_dir, 'multiple_submodules.yaml')
    nlb = NlBuilder(filename)
    result = nlb.process_text()
    # The return value should match the updated attribute
    assert result == nlb.sentence_stmts
    # There are 7 sentences in the model
    assert len(nlb.sentence_stmts) == 7
    ss_list = list(nlb.sentence_stmts.items())
    # The first statement is a Complex
    assert isinstance(ss_list[0][1][0], Complex)
    # The last statement is an ActiveForm
    assert isinstance(ss_list[-1][1][0], ActiveForm)
    # Check that the files showed up in the cache
    assert isfile(join(nlb.cache_dir, 'EGFbindsEGFR.pkl'))
    assert isfile(join(nlb.cache_dir,
                       'MAPK1phosphorylatedatT185andY187isactive.pkl'))

if __name__ == '__main__':
    test_process_text()
