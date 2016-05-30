﻿import fileinput #for reading large files
import json
import random
import numpy as np
import os
import shutil
import csv 
import math
from datetime import datetime
           
class Embedding:

    #region Reading data

    def ReadTestFile():
        with open('smalldata.json') as data_file:    
            data = json.load(data_file)
            return data

    def ReadMetaDataFile(metaDataFile):
        """File format: [id] [metadata] 
        metadata format: "first_line" "second_line" "third_line" """
        metaDataDict = dict()
        for line in fileinput.input([metaDataFile]):
            if line != "\n":   
                for items in csv.reader([line], delimiter='\t', quotechar='"'): 
                    id = items[0]     
                    items.pop(0)                             
                    metaDataDict[id] = items
        return metaDataDict

    def ReadPropertiesIntensitiesFile(propertiesIntensitiesFile):
        """File format: [id] [intensityOfProperty1] [intensityOfProperty2]... [intensityOfPropertyN]"""      
        intensitiesDict = dict()
        for line in fileinput.input([propertiesIntensitiesFile]):
            if line != "\n":   
                items = line.split()
                id = items[0]     
                items.pop(0)                             
                intensitiesDict[id] = items
        return intensitiesDict

    def ReadSimilarityGraph(simGraphFile):
        """Reads from simGraphFile, that has a format ' id1 id2 similarityScore '.
        Returns a dictionary with key = (id1, id2) and value = similarityScore."""
        similarityDict = dict()
        for line in fileinput.input([simGraphFile]):
            if line != "\n":   
                items = line.split()
                similarityDict[items[0], items[1]] = float(items[2])                
        return similarityDict
    
    def ReadSimilarityGraph(simGraphFile, indexedKeys):
        """Reads from simGraphFile, that has a format ' id1 id2 similarityScore '.
        Returns a dictionary with key = (id1, id2) and value = similarityScore."""
        similarityDict = dict()
        i=0
        for line in fileinput.input([simGraphFile]):
            if line != "\n":   
                items = line.split()
                similarityDict[items[0], items[1]] = float(items[2])
                indexedKeys.append([items[0], items[1]]) 
                i+=1
        return similarityDict

    def CombinePrefixesInPath(stringWithDots):
        listje = stringWithDots.split('.')
        path = []
        i = 0
        for item in listje:                        
            if i==0:
                prefix = item
            else:
                prefix = str(prefix + '.' + item)
            path.append(prefix)
            i+=1
        return path

    def AddInterPaths(inter_paths, paths):
        for item in inter_paths:
            list_ofPrefixes = Embedding.CombinePrefixesInPath(item)
            for prefix in list_ofPrefixes:
                paths[prefix] = Embedding.CombinePrefixesInPath(prefix)


    def readClusteringHierarchy(clusteringHierarchyFile, isEmbeddingHierarchical):
        """Reads file of format 'path id'. 
        Path has a format id1.id2.id3.id4 if there are 4 levels in clustering hierarchy.
        If idx is singleton after e.g. second level, path has a format id1.id2.idx.idx
        
        Returns a dictionary with key= id and value = [id1, id2, idr, id4] """
        paths = dict()
        if isEmbeddingHierarchical:
            inter_paths = []
            for line in fileinput.input([clusteringHierarchyFile]):
                if line != "\n":   
                    items = line.split()
                    paths[items[1]] = Embedding.CombinePrefixesInPath(items[0])
                    inter_paths.append(items[0])
            Embedding.AddInterPaths(inter_paths, paths)
        else: 
            for line in fileinput.input([clusteringHierarchyFile]):
                if line != "\n":   
                    items = line.split()
                    paths[items[1]] = ["0"]
        return paths
    
    #endregion 
    
    #region Analytics
        

    def MakeChildrenListPerParentPerLevel(pathsDict):
        dictionary = dict()
        for key in pathsDict:
            level = 0
            for parent in pathsDict[key]:  
                if (parent == key):
                    continue              
                nivo = len(pathsDict[key]) 
                toPut = 0
                if nivo > level + 1 and pathsDict[key][level] == parent and pathsDict[key][level + 1] == key:
                    toPut = 1
                else:
                    if nivo == level + 1 and pathsDict[key][level] == parent:
                        toPut = 1
                if toPut == 1:
                    if parent not in dictionary:
                        dictionary[parent] = []
                    while len(dictionary[parent]) <= level:
                        dictionary[parent].append([])
                    dictionary[parent][level].append(key)
                level +=1
        return dictionary     

    def ConvertSimilarityGraphToDistance(similarityDict):
        """Converts non-negative real-valued similary scores to distances between 0 and 1 """
        maxScore = max(similarityDict.values())
        if maxScore > 0:
            for key in similarityDict:
                similarityDict[key] = 1 - similarityDict[key] / maxScore # the distance is between 0 and 1
        else:
            for key in similarityDict:
                similarityDict[key] = 1   

    def FindChildren(parent, level, childrenDict): 
        """Returns a list of all direct children of parent at the given level. """     
        if parent in childrenDict and len(childrenDict[parent]) > level:
            return  childrenDict[parent][level]   
        else:
            return []
       
    def InitializePointsRandomlyForHierarchical(keys,  parent,  fixedCoordinate, coordinates, level):
        """All objects in keys whose coordinates are not fixed yet are assigned random coordinates with values in (0,1)"""
        for key in keys:
            if key not in fixedCoordinate:
                #coordinates[key] = np.array([random.random(), random.random(), random.random()])                  
                factor = math.pow(3, level+1)
                coordinates[key] = np.array([random.random()/factor, random.random()/factor, random.random()/factor]) - np.array([0.5/factor, 0.5/factor, 0.5/factor] )  
                if parent !=-1:
                    coordinates[key] += fixedCoordinate[parent]
    
    def InitializePointsRandomly(keys, parent, fixedCoordinate, coordinates):
        """All objects in keys whose coordinates are not fixed yet are assigned random coordinates with values in (0,1)"""
        for key in keys:
            if True:#key not in fixedCoordinate.keys():
                #coordinates[key] = np.array([random.random()/50, random.random()/50])
                coordinates[key] = np.array([random.random()/50, random.random()/50, random.random()/50])   
                if parent !=-1:
                    coordinates[key] += fixedCoordinate[parent]

    def FixCoordinatesHierarchical(keys, parent, edgesDict, fixedCoordinate, coordinates, level):
        """Implements the Stochastic Proximity Embedding algorithm to determine and fix the coordinates of objects with ids in keys.
        See https://www.researchgate.net/publication/10696705_Stochastic_proximity_embedding"""
        lambd = 1.0           
        epsilon = 0.00001             
        Embedding.InitializePointsRandomlyForHierarchical(keys, parent, fixedCoordinate, coordinates, level)#coordinates is a dictionary per parent id, value is a list of 3
        cycles = 2
        numberOfPoints = len(keys)
        steps = 1 * numberOfPoints
        delta = 1.0 / cycles
        while (lambd > 0):
            for count in range(0, steps):                
                i = random.choice(keys)
                j = random.choice(keys)
                if i != j: 
                    dist = np.linalg.norm(coordinates[i] - coordinates[j])
                    if (i,j) in edgesDict: 
                        rd = edgesDict[i,j]/math.pow(3, level+1)
                    else:
                        rd =  1/math.pow(3, level+1)
                    if dist != rd:                        
                        vec = coordinates[i] - coordinates[j]
                        incr = lambd * 0.5 * (rd - dist) * vec / (dist + epsilon)
                        if i not in fixedCoordinate:
                            coordinates[i] += incr
                        if j not in fixedCoordinate:
                            coordinates[j] += (-1) * incr                                                           
            lambd -= delta      
        for key in keys:
            fixedCoordinate[key] = coordinates[key]      
    
    def FixCoordinates(keys, parent, edgesDict, fixedCoordinate, coordinates, level, indexedKeys):
        """Implements the Stochastic Proximity Embedding algorithm to determine and fix the coordinates of objects with ids in keys.
        See https://www.researchgate.net/publication/10696705_Stochastic_proximity_embedding"""
        lambd = 1.0           
        epsilon = 0.00001             
        Embedding.InitializePointsRandomly(keys, parent, fixedCoordinate, coordinates)#coordinates is a dictionary per parent id, value is a list of 3
        cycles = 10
        numberOfPoints = len(keys)
        steps = 10 * numberOfPoints
        delta = 1.0 / cycles
        while (lambd > 0):
            for count in range(0, steps):                        
                index = random.randint(0, len(indexedKeys)-1)               
                edge = indexedKeys[index]
                i = edge[0]
                j=edge[1]                
                if i!=j and i in coordinates and j in coordinates: # a workaround, in a good dataset this should always hold
                    dist = np.linalg.norm(coordinates[i] - coordinates[j])
                    rd = edgesDict[i,j]
                    #rd = 1/math.pow(3, level+1)
                    if dist != rd:                        
                        vec = coordinates[i] - coordinates[j]
                        incr = lambd * 0.5 * (rd - dist) * vec / (dist + epsilon)                       
                        #if i not in fixedCoordinate.keys() and j not in fixedCoordinate.keys():
                        coordinates[i] += incr
                        coordinates[j] += (-1) * incr 
                        #else:
                            #if j not in fixedCoordinate.keys():
                                #coordinates[j] += (-1) * incr *2
                            #else:
                                #coordinates[i] += incr *2                                                                                      
            lambd -= delta      
        for key in keys:
            fixedCoordinate[key] = coordinates[key]      


    def RecursivelyEmbedNoGrandparent(parents, level, edgesDict, fixedCoordinate, coordinates, childrenDict):
        """Embeds the hierarchicall data set in a hiearchical manner"""
        Embedding.FixCoordinates(parents, edgesDict, fixedCoordinate, coordinates)
        for parent in parents:
            children = Embedding.FindChildren(parent, level, childrenDict)
            if len(children) > 0:
                Embedding.RecursivelyEmbed(children, level+1,  edgesDict, fixedCoordinate, coordinates, childrenDict)     
    
    def RecursivelyEmbed(parents, grandparent, level,  edgesDict, fixedCoordinate, coordinates, childrenDict, indexedKeys):
        """Embeds the hierarchical data set in a hiearchical manner"""
        Embedding.FixCoordinates(parents, grandparent, edgesDict, fixedCoordinate, coordinates, level, indexedKeys)
        for parent in parents:
            children = Embedding.FindChildren(parent, level, childrenDict)                   
            if len(children) > 0:
                Embedding.RecursivelyEmbed(children, parent, level+1,  edgesDict, fixedCoordinate, coordinates, childrenDict, indexedKeys)                         

    def RecursivelyEmbedHierarchical(parents, grandparent, level,  edgesDict, fixedCoordinate, coordinates, childrenDict):
        """Embeds the hierarchical data set in a hiearchical manner"""
        Embedding.FixCoordinatesHierarchical(parents, grandparent, edgesDict, fixedCoordinate, coordinates, level)
        for parent in parents:
            children = Embedding.FindChildren(parent, level, childrenDict)                   
            if len(children) > 0:
                Embedding.RecursivelyEmbedHierarchical(children, parent, level+1,  edgesDict, fixedCoordinate, coordinates, childrenDict)     
    
    def ComputeDistance(a,b, edgesDict, level, childrenDict):
        if a==b:
            return 0
        if (a,b) in edgesDict:
            return edgesDict[a,b]
        if (b,a) in edgesDict:
            return edgesDict[b,a]
        else:
            children_a = Embedding.FindChildren(a, level, childrenDict)
            children_b = Embedding.FindChildren(b, level, childrenDict)
            if len(children_a) > 0 and len(children_b)> 0:
                return Embedding.AverageDistance(children_a, children_b, level+1, edgesDict, childrenDict)
            else:
                if len(children_a) > 0:
                    return Embedding.AverageDistance(children_a, [b], level+1, edgesDict, childrenDict)
                else: 
                    if len(children_b) > 0:
                        return Embedding.AverageDistance([a], children_b, level+1, edgesDict,  childrenDict)
                    else: #if both sets of children are empty
                        return 2

    def AverageDistance(set1, set2, level, edgesDict, childrenDict):
        averageDist = 0
        for i in set1:
            for j in set2:
                #if (i,j) not in edgesDict:
                dist = Embedding.ComputeDistance(i, j, edgesDict, level, childrenDict)
                #edgesDict[i,j] = dist
                #else:
                    #dist = edgesDict[i,j]
                averageDist += dist
        averageDist /= len(set1) * len(set2)
        return averageDist

    def RecursivelyComputeDistances(set, level, edgesDict, childrenDict):
        for key in set:
            children=Embedding.FindChildren(key, level, childrenDict)
            if len(children) > 0:
                 Embedding.RecursivelyComputeDistances(children, level+1, edgesDict, childrenDict)
        for i in range(0, len(set)):
            for j in range(0, len(set)):  
                if (i,j) not in edgesDict:                   
                    dist = Embedding.ComputeDistance(set[i], set[j], edgesDict, level, childrenDict)
                    edgesDict[set[i],set[j]] = dist

    #def AverageDistance(set1, set2, level, edgesDict, childrenDict):
    #    averageDist = 0
    #    for i in set1:
    #        j = random.choice(set2)
    #        dist = Embedding.ComputeDistance(i, j, edgesDict, level, childrenDict)
    #        averageDist += dist
    #    averageDist /= len(set1) * len(set2)
    #    return averageDist

    #def RecursivelyComputeDistances(set, level, edgesDict, childrenDict):        
    #    for i in range(0, len(set)-2):
    #        for j in range(i+1, len(set)-1):     
    #            if (set[i], set[j]) not in edgesDict:                                                    
    #                dist = Embedding.ComputeDistance(set[i], set[j], edgesDict, level, childrenDict)
    #                edgesDict[set[i],set[j]] = dist    
    #endregion

    #region Write output

    def CreateDataJSONFile(allPoints, parentsKeys, startingFolder):
        currentPoints= dict()
        for key in parentsKeys:
            if key in allPoints:# a workaround, in a good dataset this should always hold
                currentPoints[key] = allPoints[key]
        string = json.dumps(currentPoints)
        file = open(startingFolder + "\\data.json", "x")
        file.write(string)
        file.close()

    def RecursivelyCreateDataFileAndFolders(allPoints, parentsKeys, level, startingFolder, childrenDict):#allPoints is a dict where keys are id's and values are Point objects    
        Embedding.CreateDataJSONFile(allPoints, parentsKeys, startingFolder)
        for parent in parentsKeys:
            childrenKeys = Embedding.FindChildren(parent, level, childrenDict)
            if len(childrenKeys) > 0:
                Embedding.CreateDirIfDoesNotExist(startingFolder + "\\" + parent)
                Embedding.RecursivelyCreateDataFileAndFolders(allPoints, childrenKeys, level+1, startingFolder + "\\" + parent, childrenDict)       
    
    def CreateSmallDataJSONFile(allPoints, startingFolder):
        string = json.dumps(allPoints)
        file = open(startingFolder + "\\smalldata.json", "x")
        file.write(string)
        file.close()
   
    def CreateMetaDataFileForBigDataMode(startingFolder, bigdatamode):
        string = "var bigData =" + bigdatamode + ";"
        file = open(startingFolder + "\\MetaData.js", "x")
        file.write(string)
        file.close()

    def CreatePointsDictionary(fixedCoordinates, pathsDict, metaDataDict, intensitiesOfPropertiesDict):
        pointsDict = dict()
        for key in pathsDict:
            point = dict()
            point["Path"] = pathsDict[key]
            point["Coordinates"] = fixedCoordinates[key]
            #point["Coordinates"].append(0)
            if (metaDataDict != "no" ):
                if key in metaDataDict:
                    point["Categories"] = metaDataDict[key]
                else:
                    point["Categories"] = []
            if (intensitiesOfPropertiesDict != "no"):                
                point["Properties"] = intensitiesOfPropertiesDict[key]
            else: 
                point["Properties"] = []
            pointsDict[key] = point
        return pointsDict

    def CreateDirIfDoesNotExist(dirname):
        if not os.path.exists(dirname):          
            os.makedirs(dirname)

    def RemoveDirTreeIfExists(dirname):        
        if os.path.exists(dirname):
            shutil.rmtree(dirname)

    #endregion 

    #region Workflow
    def ExtractRoots(pathsDict):
        roots = []
        for path in pathsDict.values():
            roots.append(path[0])
        roots = list(set(roots))
        return roots

    def ConvertCoordinatesToList(fixedCoordinate):
        for key in fixedCoordinate:
            fixedCoordinate[key] = list(fixedCoordinate[key])
                       
    def Workflow(simGraphFile, clusteringHierarchyFile, metaDataFile, namesOfPropertiesFile, propertiesIntensitiesFile, bigDataMode = "true", isEmbeddingHierarchical= True):
        """ Runs all functions to read, embed in 3D and write data.
        simGraphFile contains the sparse similarity matrix.  Format: [id1] [id2]  [similarityScore] 
        clusteringHierarchyFile contains path in tree for every id. Format: [parent1ID.parent2ID.parent3ID.....parentNID] [id]
        metaDataFile contains text that is displayed for every point. Format: [id] ["line1text"] ["line2text"] ... ["lineNtext"]
        namesOfPropertiesFile contains the names of the properties, the intensities of which are given in file propertiesIntensitiesFile. It must be a json file. Format : [ ["PropertyName1", "PropertyName2", ... "PropertyNameN"] ]. E.g. ["Age", "Size"]       
        propertiesIntensitiesFile contains the intensities of the properties per point. Format: [id] [intensityProperty1] [intensityProperty2] ... [intensityPropertyN]
        bigDataMode is "true" or "false", depending on the mode in which the application should run. If "false", then there is a slidebar for loading all points up to a level"""        
        print(str(datetime.now()) + ": Removing old data...")
        dirname1 = "\\\\?\\" + os.getcwd() + "\\" + "data"
        Embedding.RemoveDirTreeIfExists(dirname1)
        print(str(datetime.now()) + ": Reading input files...")
        if metaDataFile != "No":
            metaDataDict = Embedding.ReadMetaDataFile(metaDataFile)
        else: 
            metaDataDict = "no"
        if propertiesIntensitiesFile != "No":
            intensitiesDict = Embedding.ReadPropertiesIntensitiesFile(propertiesIntensitiesFile)
        else:
            intensitiesDict = "no"
        indexedKeys = []
        if isEmbeddingHierarchical:
            edgesDict = Embedding.ReadSimilarityGraph(simGraphFile, indexedKeys)
        else: 
            edgesDict = Embedding.ReadSimilarityGraph(simGraphFile,indexedKeys)
        Embedding.ConvertSimilarityGraphToDistance(edgesDict)
        pathsDict = Embedding.readClusteringHierarchy(clusteringHierarchyFile, isEmbeddingHierarchical)
        childrenDict = Embedding.MakeChildrenListPerParentPerLevel(pathsDict)
        fixedCoordinate = dict()
        coordinates = dict()
        print(str(datetime.now()) + ": Start embedding...")
        roots = Embedding.ExtractRoots(pathsDict)        
        if isEmbeddingHierarchical:
            #print(str(datetime.now()) + ": Start computing distances...")
            #Embedding.RecursivelyComputeDistances(roots, 0, edgesDict, childrenDict)
            print(str(datetime.now()) + ": Start embedding hierarchical...")
            Embedding.RecursivelyEmbedHierarchical(roots, -1, 0, edgesDict, fixedCoordinate, coordinates, childrenDict)
        else:
            Embedding.RecursivelyEmbed(roots, -1, 0, edgesDict, fixedCoordinate, coordinates, childrenDict, indexedKeys)
        Embedding.ConvertCoordinatesToList(fixedCoordinate)
        pointsDict = Embedding.CreatePointsDictionary(fixedCoordinate, pathsDict, metaDataDict, intensitiesDict)        
        print(str(datetime.now()) + ": Start writing output...") 
        
        Embedding.CreateDirIfDoesNotExist(dirname1)
        Embedding.RecursivelyCreateDataFileAndFolders(pointsDict, roots, 0, dirname1, childrenDict)
        if bigDataMode == "false": 
            Embedding.CreateSmallDataJSONFile(pointsDict, "data")
        shutil.copyfile(namesOfPropertiesFile, "data/NamesOfProperties.json")
        Embedding.CreateMetaDataFileForBigDataMode("data", bigDataMode)
        print(str(datetime.now()) + ": Finished writing output.")
    #endregion
         
#region Main

#calling in hierarchical embedding mode

Embedding.Workflow("sim.txt", "clusters.txt", "oma-hogs_banana.meta", "NamesOfProperties.json","No", "false", True )
#calling in flat embedding mode
#Embedding.Workflow("MUSAC-MUSAM.graph", "oma-hogs_banana.cls", "oma-hogs_banana.meta", "NamesOfProperties.json","No", "false", False)
#endregion

