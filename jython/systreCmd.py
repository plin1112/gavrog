#!/bin/env jython

import optparse
import os.path
import sys

import java.io
import java.util

import org.gavrog


def pluralize(n, s):
    return "%d %s%s" % (n, s, "s" if n > 1 else "")


def isArchiveFileName(filename):
    return os.path.splitext(filename)[1] == '.arc'


def makeArchive(reader=None):
    archive = org.gavrog.joss.pgraphs.io.Archive('1.0')
    if reader:
        archive.addAll(reader)
    return archive


def readBuiltinArchive(name):
    loader = java.lang.ClassLoader.getSystemClassLoader()
    rcsrPath = "org/gavrog/apps/systre/%s" % name
    rcsrStream = loader.getResourceAsStream(rcsrPath)

    return makeArchive(java.io.InputStreamReader(rcsrStream))


def readArchiveFromFile(fname):
    return makeArchive(java.io.FileReader(fname))


def prefixedLineWriter(prefix=''):
    def write(s=''):
        print "%s%s" % (prefix, s)

    return write


def reportSystreError(errorType, message, writeInfo):
    writeInfo("!!! ERROR (%s) - %s." % (errorType, message))


def nodeNameMapping(phi):
    imageNode2Orbit = {}
    for orbit in phi.imageGraph.nodeOrbits():
        for v in orbit:
            imageNode2Orbit[v] = orbit

    orbit2name = {}
    node2name = {}
    mergedNames = []
    mergedNamesSeen = set()

    for v in phi.sourceGraph.nodes():
        name = phi.sourceGraph.getNodeName(v)
        w = phi.getImage(v)
        orbit = imageNode2Orbit[w]

        if name != orbit2name.get(orbit, name):
            pair = (name, orbit2name[orbit])
            if pair not in mergedNamesSeen:
                mergedNames.append(pair)
                mergedNamesSeen.add(pair)
        else:
            orbit2name[orbit] = name

        node2name[w] = orbit2name[orbit]

    return node2name, mergedNames


def processDisconnectedGraph(
    graph,
    options,
    writeInfo=prefixedLineWriter(),
    writeData=prefixedLineWriter(),
    lookupArchives={},
    runArchive=makeArchive(),
    outputArchiveFp=None):

    writeInfo("   Structure is not connected.")
    writeInfo("   Processing components separately.")
    writeInfo()

    #TODO implement this


def processGraph(
    graph,
    options,
    writeInfo=prefixedLineWriter(),
    writeData=prefixedLineWriter(),
    lookupArchives={},
    runArchive=makeArchive(),
    outputArchiveFp=None):

    d = graph.dimension
    n = graph.numberOfNodes()
    m = graph.numberOfEdges()

    writeInfo("   Input structure described as %d-periodic." % d)
    writeInfo("   Given space group is %s." % graph.givenGroup)
    writeInfo("   %s and %s in repeat unit as given." % (
            pluralize(n, "node"), pluralize(m, "edge")))
    writeInfo()

    if not graph.isConnected():
        return processDisconnecteGraph(
            G,
            options,
            writeInfo=writeInfo,
            writeData=writeData,
            lookupArchives=lookupArchives,
            runArchive=runArchive,
            outputArchiveFp=outputArchiveFp)

    pos = graph.barycentricPlacement()

    if not graph.isLocallyStable():
        msg = ("Structure has collisions between next-nearest neighbors."
               + " Systre does not currently support such structures.")
        return reportSystreError("STRUCTURE", msg, writeInfo)

    if graph.isLadder():
        msg = "Structure is non-crystallographic (a 'ladder')"
        return reportSystreError("STRUCTURE", msg, writeInfo)

    if graph.hasSecondOrderCollisions():
        msg = ("Structure has second-order collisions."
               + " Systre does not currently support such structures.")
        return reportSystreError("STRUCTURE", msg, writeInfo)

    if not graph.isStable():
        writeInfo("Structure has collisions.")
        writeInfo()

    M = graph.minimalImageMap()
    G = M.imageGraph

    if G.numberOfEdges() < m:
        writeInfo("   Ideal repeat unit smaller than given (%d vs %d edges)."
                  % (G.numberOfEdges(), m))
    else:
        writeInfo("   Given repeat unit is accurate.")

    ops = G.symmetryOperators()

    writeInfo("   Point group has %d elements." % len(ops))
    writeInfo("   %s of node." % pluralize(len(list(G.nodeOrbits())), "kind"))
    writeInfo()

    nodeToName, mergedNames = nodeNameMapping(M)

    writeInfo("   Equivalences for non-unique nodes:")
    for old, new in mergedNames:
        writeInfo("      %s --> %s" % (old, new))
    writeInfo()


def processDataFile(
    fname,
    options,
    writeInfo=prefixedLineWriter(),
    writeData=prefixedLineWriter(),
    lookupArchives={},
    runArchive=makeArchive(),
    outputArchiveFp=None):

    count = 0
    fileBaseName = os.path.splitext(os.path.basename(fname))[0]

    writeInfo("Data file %s" % fname)

    for G in org.gavrog.joss.pgraphs.io.Net.iterator(fname):
        writeData()
        if count:
            writeData()
            writeData()

        count += 1

        name = G.name or "%s-#%03d" % (fileBaseName, count)

        writeInfo("Structure #%d - %s" % (count, name))
        writeData()

        hasWarnings = False
        for text in G.warnings:
            writeInfo("   (%s)" % text)
            hasWarnings = True

        if hasWarnings:
            writeData()

        hasErrors = False
        for err in G.errors:
            writeInfo("!!! ERROR (INPUT) - %s" % err.message)
            hasErrors = True

        if hasErrors:
            continue

        processGraph(
            G,
            options,
            writeInfo=writeInfo,
            writeData=writeData,
            lookupArchives=lookupArchives,
            runArchive=runArchive,
            outputArchiveFp=outputArchiveFp)

        writeInfo("Finished structure #%d - %s" % (count, name))

    writeData()
    writeInfo("Finished data file \"%s\"." % fname)


def parseOptions():
    parser = optparse.OptionParser("usage: %prog [OPTIONS] FILE...")

    parser.add_option('-a', '--output-archive-name', metavar='FILE',
                      dest='outputArchiveName', type='string',
                      help='file name for optional output archive')
    parser.add_option('-b', '--barycentric',
                      dest='relaxPositions',
                      default=True, action='store_false',
                      help='output barycentric instead of relaxed positions')
    parser.add_option('-c', '--output-format-cgd',
                      dest='outputFormatCGD',
                      default=False, action='store_true',
                      help='produce .cgd file format instead of default output')
    parser.add_option('-d', '--duplicate-is-error',
                      dest='duplicateIsError',
                      default=False, action='store_true',
                      help='terminate if a net is encountered twice')
    parser.add_option('-e', '--equal-edge-priority', metavar='N',
                      dest='relaxPasses', type='int', default=3,
                      help='equal edge lengths priority (default 3)')
    parser.add_option('-f', '--prefer-first-origin',
                      dest='preferSecondOrigin',
                      default=True, action='store_false',
                      help='prefer first over second origin')
    parser.add_option('-k', '--output-systre-key',
                      dest='outputSystreKey',
                      default=False, action='store_true',
                      help='include the Systre key in the output')
    parser.add_option('-n', '--no-builtin',
                      dest='useBuiltinArchive',
                      default=True, action='store_false',
                      help='do not use the builtin Systre archive')
    parser.add_option('-r', '--prefer-rhombohedral',
                      dest='preferHexagonal',
                      default=True, action='store_false',
                      help='prefer rhombohedral over hexagonal setting')
    parser.add_option('-s', '--relaxation-steps', metavar='N',
                      dest='relaxSteps', type='int', default=10000,
                      help='iterations in net relaxation (default 10000)')
    parser.add_option('-t', '--skip-embedding',
                      dest='computeEmbedding',
                      default=True, action='store_false',
                      help='do not compute embeddings for nets')
    parser.add_option('-u', '--full-unit-cell',
                      dest='outputFullCell',
                      default=False, action='store_true',
                      help='output full unit cell, not just repeat unit')
    parser.add_option('-x', '--archives-as-input',
                      dest='archivesAsInput',
                      default=False, action='store_true',
                      help='process archive files as normal net input')

    return parser.parse_args()


def run():
    options, args = parseOptions()

    if options.archivesAsInput:
        inputFileNames = args
        archiveFileNames = []
    else:
        archiveFileNames = filter(isArchiveFileName, args)
        inputFileNames = filter(lambda s: not isArchiveFileName(s), args)

    lookupArchives = {}
    if options.useBuiltinArchive:
        lookupArchives['__rcsr__'] = readBuiltinArchive('rcsr.arc')

    for fname in archiveFileNames:
        lookupArchives[fname] = readArchiveFromFile(fname)

    runArchive = makeArchive()

    arcFp = options.outputArchiveName and file(options.outputArchiveName, 'wb')

    infoPrefix = '## ' if options.outputFormatCGD else ''

    try:
        for name in inputFileNames:
            processDataFile(
                name,
                options,
                writeInfo=prefixedLineWriter(infoPrefix),
                writeData=prefixedLineWriter(),
                lookupArchives=lookupArchives,
                runArchive=runArchive,
                outputArchiveFp=arcFp)
    finally:
        if arcFp:
            arcFp.flush()
            arcFp.close()


if __name__ == "__main__":
    java.util.Locale.setDefault(java.util.Locale.US)

    run()