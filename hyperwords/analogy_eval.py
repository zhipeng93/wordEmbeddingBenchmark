from __builtin__ import sorted

from docopt import docopt
import numpy as np

from representations.representation_factory import create_representation


def main():
    args = docopt("""
    Usage:
        analogy_eval.py [options] <representation> <representation_path> <task_path>
    
    Options:
        --neg NUM    Number of negative samples; subtracts its log from PMI (only applicable to PPMI) [default: 1]
        --w+c        Use ensemble of word and context vectors (not applicable to PPMI)
        --eig NUM    Weighted exponent of the eigenvalue matrix (only applicable to SVD) [default: 0.5]
        --norm       whether normalize 
    """)
    
    data = read_test_set(args['<task_path>'])
    xi, ix = get_vocab(data) # xi is a dict, {word:id}, ix is a set, {word}.
    representation = create_representation(args)
    accuracy_add, accuracy_mul, accuracy_kl = evaluate(representation, data, xi, ix)
    print args['<representation>'], args['<representation_path>'], 
    '\t%0.3f' % accuracy_add, '\t%0.3f' % accuracy_mul, '\t%0.3f' % accuracy_kl
    print "representation\tpmi_file\tneg_num\tnorm\ttask_path\taccur_add\taccur_mult\taccur_kl\t"
    print args['<representation>'], args['<representation_path>'], args['--neg'], args['--norm'], args['<task_path>'], '\t%0.3f' % accuracy_add, '\t%0.3f' % accuracy_mul, '\t%0.3f' % accuracy_kl


def read_test_set(path):
    test = []
    with open(path) as f:
        for line in f:
            analogy = line.strip().lower().split()
            test.append(analogy)
    return test 


def get_vocab(data):
    vocab = set()
    for analogy in data:
        vocab.update(analogy)
    vocab = sorted(vocab)
    return dict([(a, i) for i, a in enumerate(vocab)]), vocab


def evaluate(representation, data, xi, ix):
    sims = prepare_similarities(representation, ix)
    #sims = prepare_KL(representation, ix, 1e-2) 
    # KL is too slow because matrix multiplication in python is optimized.

    correct_add = 0.0
    correct_mul = 0.0
    correct_kl = 0.0 # compute the most similar pmi(a, a_), pmi(b, b_)
    for a, a_, b, b_ in data:
        b_add, b_mul = guess(representation, sims, xi, a, a_, b)
        #b_kl = guess_kl(representation, sims, xi, a, a_, b)
        #if b_kl == b_:
        #    correct_kl += 1
        if b_add == b_:
            correct_add += 1
        if b_mul == b_:
            correct_mul += 1
    return correct_add/len(data), correct_mul/len(data), correct_kl/len(data)


#def pmi_guess(representation, xi, a, a_, b):
#    # find b_ satisfy that pmi(a, a_) == pmi(b, b_)
#    if a in representation.wi:
#        if a_ in representation.wi:
#            if b in representation.wi:
#                tmp = representation.m[representation.wi[a]][representation.wi[a_]]

def kl(a, b, threshold):
    assert len(a) == len(b)
    sum = 0
    for i in xrange(0, len(a)):
        if a[i] < threshold or b[i] < threshold:
            continue
        else:
            sum += a[i] * np.log(a[i] / b[i])

    return sum

def prepare_KL(representation, vocab, threshold):
    # precompute the similaritys with others.
    vocab_representation = representation.m[[representation.wi[w] if w in representation.wi else 0 for w in vocab]]

    # sims = vocab_representation.dot(representation.m.T). Using threshold-based KL divergence instead.
    vocab_size = vocab_representation.shape[0]
    repre_size = representation.m.shape[0]
    sims = np.zeros( (vocab_size, repre_size) )
    for i in xrange(vocab_size):
        for j in xrange(repre_size):
            # need to replace with kl. But maybe too slow.
            tmp = vocab_representation[i, :].dot(representation.m[:, j])
            #print type(tmp)
            sims[i][j] = tmp[0, 0]

    # Assuming there are 100 words in the test sets, 1000 words in the whole vocabulary, sims is an 100 * 1000 matrix.
    # if the word in testsets are not in corpus, the similarity of that word with others are defined to be zero.
    dummy = None
    for w in vocab:
        if w not in representation.wi:
            dummy = representation.represent(w)
            break
    if dummy is not None:
        for i, w in enumerate(vocab):
            if w not in representation.wi:
                vocab_representation[i] = dummy

    if type(sims) is not np.ndarray:
        sims = np.array(sims.todense())
    else:
        sims = (sims + 1) / 2  # used for cosine, normalize to (0, 1).
    return sims


def prepare_similarities(representation, vocab):
    # precompute the similaritys with others.
    vocab_representation = representation.m[[representation.wi[w] if w in representation.wi else 0 for w in vocab]]

    sims = vocab_representation.dot(representation.m.T)
    # Assuming there are 100 words in the test sets, 1000 words in the whole vocabulary, sims is an 100 * 1000 matrix.
    # if the word in testsets are not in corpus, the similarity of that word with others are defined to be zero.
    dummy = None
    for w in vocab:
        if w not in representation.wi:
            dummy = representation.represent(w)
            break
    if dummy is not None:
        for i, w in enumerate(vocab):
            if w not in representation.wi:
                vocab_representation[i] = dummy
    
    if type(sims) is not np.ndarray:
        sims = np.array(sims.todense())
    else:
        sims = (sims+1)/2  # used for cosine, normalize to (0, 1).
    return sims


def guess_kl(representation, sims, xi, a, a_, b):
    # min |kl(a, a_) - kl(b, b_)|
    kl_a_a_ = sims[xi[a]][xi[a_]] # kl(a, a_)
    tmp = sims[xi[b]] - kl_a_a_
    return abs(tmp).argmin()


def guess(representation, sims, xi, a, a_, b):
    sa = sims[xi[a]] # cos(a, b*)
    sa_ = sims[xi[a_]] # cos(a*, b*)
    sb = sims[xi[b]] # cos(b, b*)
    
    add_sim = -sa+sa_+sb
    if a in representation.wi:
        add_sim[representation.wi[a]] = 0
    if a_ in representation.wi:
        add_sim[representation.wi[a_]] = 0
    if b in representation.wi:
        add_sim[representation.wi[b]] = 0
    b_add = representation.iw[np.nanargmax(add_sim)]
    # returns the index of maximum values ignoring NANs.
    
    mul_sim = sa_*sb*np.reciprocal(sa+0.01)
    if a in representation.wi:
        mul_sim[representation.wi[a]] = 0
    if a_ in representation.wi:
        mul_sim[representation.wi[a_]] = 0
    if b in representation.wi:
        mul_sim[representation.wi[b]] = 0
    b_mul = representation.iw[np.nanargmax(mul_sim)]
    
    return b_add, b_mul


if __name__ == '__main__':
    main()
