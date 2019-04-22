"""
various subprocess wrappers, mainly for parsing and
token-based preprocessing in parsing
"""
from __future__ import print_function
from __future__ import absolute_import
from builtins import str
import optparse
import os.path
import sys
from subprocess import Popen, PIPE
import logging

from .util import get_config_var, load_plugin
from . import penn, tree

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())
# logger.addHandler(logging.NullHandler())


def remove_quotes(words):
    '''
    removes the quotes from a sentence. Returns the sentence without quotes
    and a list of removed tokens and their offsets.
    '''
    tokens = words[:]
    punct = []
    pos = 0
    while pos < len(tokens):
        if tokens[pos] in ['"', "'", '...', '`', '/', "''", "``"]:
            punct.append((pos, tokens[pos]))
            del tokens[pos]
        elif tokens[pos:pos + 3] == ['.', '.', '.']:
            punct.append((pos, '.'))
            punct.append((pos, '.'))
            punct.append((pos, '.'))
            del tokens[pos:pos + 3]
        else:
            pos += 1
    punct.reverse()
    return (tokens, punct)


def reinsert_punctuation(tokens, punct):
    '''
    reinserts the punctuation from remove_quotes
    at the appropriate indices
    '''
    for pos, token in punct:
        tokens[pos:pos] = token
    return tokens


def reinsert_punctuation_tree(t, punct, punct_tag='$('):
    """reinsert punctuation into the current tree"""
    for pos, token in punct:
        new_node = tree.TerminalNode(punct_tag, token, '--')
        t.terminals[pos:pos] = [new_node]
        t.roots.append(new_node)
    for pos, node in enumerate(t.terminals):
        node.start = pos
        node.end = pos + 1
    t.determine_tokenspan_all()


class LineBasedWrapper(object):
    """
    process-based wrapper that (normally) processes things
    line by line
    """
    def __init__(self, cmd, env=None):
        '''creates a wrapper for a command process.
        we don't create the process right away; rather,
        we do that when it's used for the first time.
        This means that creating a LineBasedWrapper in
        multiprocessing will create multiple child processes
        for that command'''
        self.cmd = cmd
        self.env = env
        self.stdin = self.stdout = self.proc = None

    def process_line(self, line):
        """processes a line"""
        if self.proc is None:
            self.proc = Popen(self.cmd,
                              shell=False,
                              stdin=PIPE, stdout=PIPE,
                              env=self.env,
                              close_fds=True)
            (self.stdin, self.stdout) = (self.proc.stdin, self.proc.stdout)
        logger.debug("Write to %s", self.cmd)
        logger.debug("Write data: %s", line)
        self.stdin.write(line.rstrip('\n'))
        self.stdin.write('\n')
        self.stdin.flush()
        return self.stdout.readline()

    def process_tokens(self, tokens):
        """assuming the line consists of space-separated tokens,
        processes the given tokens"""
        result = self.process_line(' '.join(tokens))
        return result.strip().split()

# pylint:disable=R0903


class BonsaiPreprocess(object):

    """preprocessing pipeline for the french Bonsai
    wrapper around Berkeley"""

    def __init__(self, bonsai_dir):
        self.bonsai_dir = bonsai_dir
        cmds = [[os.path.join(bonsai_dir, 'src/do_desinflect.py'),
                 '--serializedlex', '--inputformat', 'tok',
                 os.path.join(bonsai_dir, 'resources/lefff/lefff')],
                [os.path.join(bonsai_dir, 'src/do_substitute_tokens.py'),
                 '--inputformat', 'tok',
                 '--ldelim', '-K', '--rdelim', 'K-',
                 os.path.join(
                     bonsai_dir,
                     'resources/clusters/EP.tcs.dfl-c1000-min20-v2.utf8')]]
        self.wrappers = [LineBasedWrapper(['python', '-u'] + cmd)
                         for cmd in cmds]
        # need to follow up by recode to latin1... why?

    def process_line(self, line):
        """runs one line through all preprocessing steps, then the parser."""
        result = line
        for wrapper in self.wrappers:
            result = wrapper.process_line(result)
        return result


class ParserWrapper(object):

    """
    adds functionality such as punctuation removal and assorted goodies.
    """

    def __init__(self, parser,
                 preprocess=None,
                 punct=None,
                 postprocess=None):
        self.parser = parser
        self.punct = punct
        self.preprocess = preprocess
        if postprocess:
            self.postprocess = postprocess
        else:
            self.postprocess = []

    def do_parse(self, s):
        """the actual parsing"""
        parsed = self.parser.do_parse(s)
        if parsed is None:
            return None
        t = tree.Tree()
        t.terminals = []
        t.roots = parsed.children
        for n in t.roots:
            n.parent = None
        penn.number_ids(t, parsed)
        parsed.id = 0
        return t

    def __call__(self, words):
        if self.punct == 'remove_quotes':
            words0, punct = remove_quotes(words)
        else:
            words0 = words
        if len(words0) == 0:
            return None
        words1 = [w.replace(' ', '_') for w in words0]
        s = ' '.join(words1)
        if isinstance(s, str):
            s = s.encode('UTF-8')
        if self.preprocess:
            for proc in self.preprocess:
                s = proc.process_line(s)
        t = self.do_parse(s)
        if t is None:
            return None
        assert len(t.terminals) == len(words0), (t.terminals, words0)
        for w, n in zip(words0, t.terminals):
            n.word = w
        if self.punct == 'remove_quotes':
            reinsert_punctuation_tree(t, punct)
        for proc in self.postprocess:
            proc(t)
        return t


class BerkeleyWrapper(LineBasedWrapper):

    '''
    wraps a process that runs the Berkeley parser.
    '''
    # pylint:disable=W0102,R0913

    def __init__(self, jarfile, model,
                 java_flags=['-Xmx1800m', '-server'],
                 parser_flags=['-accurate'],
                 parens=None):
        LineBasedWrapper.__init__(self,
                                  ['java'] + java_flags +
                                  ['-jar', jarfile, '-gr', model] +
                                  parser_flags)
        if parens is None:
            self.lparen = '-LRB-'
            self.rparen = '-RRB-'
        else:
            self.lparen = parens[0]
            self.rparen = parens[1]

    def do_parse(self, s):
        """the actual parsing"""
        s = s.replace('(', self.lparen)
        s = s.replace(')', self.rparen)
        result = self.process_line(s).rstrip('\n')
        if result[:4] == '( ( ' and result[-2:] == ' )':
            # BerkeleyParser sometimes does this
            result = result[2:-2]
        if result[:2] == '( ':
            result = '(ROOT ' + result[2:]
        # BUBS sometimes does this, and it's annoying
        if result == 'java.lang.NullPointerException':
            result = self.stdout.readline()
        if result in ['(ROOT)', '(())', '()']:
            return None
        logger.debug('line2parse: %s', result)
        parsed = penn.line2parse(result)
        return parsed


class BUBSWrapper(BerkeleyWrapper):

    '''wraps the BUBS parser'''
    # pylint:disable=W0102,W0231,W0233,R0913

    def __init__(self, jarfile, model, fom, beam,
                 java_flags=['-Xmx1800m', '-server',
                             '-XX:+UseParallelGC',
                             '-XX:+UseParallelOldGC'],
                 parser_flags=[],
                 preprocess=None):
        LineBasedWrapper.__init__(
            self,
            ['java'] + java_flags + ['-jar', jarfile, '-g', model,
                                     '-fom', fom, '-beamModel', beam,
                                     '-if', 'Token', '-v', 'warning'])
        self.preprocess = preprocess
        print("running:", ' '.join(self.cmd), file=sys.stderr)


# pylint:disable=C0103
def BonsaiPipeline(bonsai_dir, **kw):
    '''creates a Bonsai parser pipeline given the bonsai root dir'''
    preproc = BonsaiPreprocess(bonsai_dir)
    parser = BerkeleyWrapper(
        os.path.join(bonsai_dir,
                     'resources/bkyjar/berkeleyParser-V1_0-fr.jar'),
        os.path.join(bonsai_dir,
                     'resources/bkygram/gram-ftbuc+dfl+clust0-200-v6'),
        **kw)
    wrapper = ParserWrapper(parser=parser, preprocess=preproc)
    return wrapper


def make_bubs_pipeline(bubs_dir):
    '''creates an English parser pipeline given the BUBS root dir'''
    parser = BUBSWrapper(os.path.join(bubs_dir, 'parse.jar'),
                         os.path.join(bubs_dir, 'eng.sm6.gr.gz'),
                         os.path.join(bubs_dir, 'eng.sm6.fom.gz'),
                         os.path.join(bubs_dir, 'eng.sm6.bcm.gz'))
    return ParserWrapper(parser)


def make_mate_lemmatizer(model_name):
    '''creates a pipeline component for MATE's lemmatizer, based on
    the custom examples.Lemmatize code'''
    mate_dir = get_config_var('mate.mate_dir')
    model_fname = os.path.join(
        mate_dir, 'models',
        get_config_var('mate.lemmatizer_models.' + model_name))
    cmd = ['java', '-cp',
           ('%(mdir)s/dist/anna-3.jar:%(mdir)s/lib/commons-lang3-3.1.jar:' +
            '%(mdir)s/lib/commons-math-2.2.jar:' +
            '%(mdir)slib/trove-2.0.4.jar') % {'mdir': mate_dir},
           'examples.Lemmatize',
           model_fname]
    return LineBasedWrapper(cmd)


def make_token_pipeline(descr):
    '''creates a token-rewriting pipeline according to the specification'''
    part = descr.split('/')
    if part[0] == 'mate_lemma':
        return make_mate_lemmatizer(part[1])
    elif part[0] == 'bonsai':
        bonsai_dir = get_config_var('bonsai.bonsai_dir')
        return BonsaiPreprocess(bonsai_dir)
    elif part[0] == 'rdt':
        unkword_dir = get_config_var('unkword_dir')
        from pynlp.tag_clusters import make_rdt_tagger
        return make_rdt_tagger(os.path.join(unkword_dir,
                                            'rdt', part[1],
                                            part[2] + '.json'),
                               os.path.join(unkword_dir,
                                            'vocabulary', part[1],
                                            part[3] + '.txt'))


def make_parser_pipeline(descr):
    '''
    returns a parser pipeline given a name such as
    DE/r6train
    '''
    if descr == 'bonsai':
        return BonsaiPipeline(get_config_var('bonsai.bonsai_dir'),
                              parser_flags=[])
    elif descr == 'bubs':
        return make_bubs_pipeline(get_config_var('bubs.bubs_dir'))
    part = descr.split('/')
    stuff = get_config_var('parsing.models.' + '.'.join(part))
    return parser_from_yaml(stuff)


def make_postprocessor(descr):
    """retrieves/creates a certain postprocessor"""
    return load_plugin('tree_transform', descr)


def parser_from_yaml(stuff):
    '''
    given a description (from YAML or JSON),
    constructs a matching parsing pipeline
    '''
    tp = stuff['type']
    if tp in ['bky', 'bkylab']:
        model_dir = get_config_var('parsing.berkeley.model_dir')
        bky_jar = get_config_var('parsing.berkeley.default_jar')
        model_fname = os.path.join(model_dir, stuff['model'])
        parens = stuff.get('parens', None)
        token_pipelines = [make_token_pipeline(arg)
                           for arg in stuff['preproc']]
        postprocess = [make_postprocessor(arg)
                       for arg in stuff['postproc']]
        try:
            from pynlp_jcc.bp_wrapper import BerkeleyJCCWrapper
            parser = BerkeleyJCCWrapper(model_fname, parens=parens)
        except ImportError:
            parser = BerkeleyWrapper(bky_jar, model_fname, parens=parens)
        wrapper = ParserWrapper(parser,
                                token_pipelines,
                                punct=stuff.get('punct', None),
                                postprocess=postprocess)
        return wrapper


token_pipeline_opt = optparse.OptionParser()


def token_pipeline_main(argv=None):
    '''
    constructs a token pipeline and applies it to the data provided
    in stdin, writes it to stdout.
    '''
    # pylint:disable=W0612
    opts, args = token_pipeline_opt.parse_args(argv)
    pipelines = [make_token_pipeline(arg) for arg in args]
    for line in sys.stdin:
        line2 = line
        for pipeline in pipelines:
            line2 = pipeline.process_line(line)
        sys.stdout.write(line2)
