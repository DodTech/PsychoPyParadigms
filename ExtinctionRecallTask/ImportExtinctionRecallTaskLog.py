#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
ImportExtinctionRecallTaskLog.py

Helper functions for ImportExtinctionRecallTaskLog_batch.py.

Created 1/3/19 by DJ.
Updated 1/10/19 by DJ - adjusted to new VAS logging format, added GetVasTypes.
Updated 1/11/19 by DJ - bug fixes, comments.
Updated 2/25/19 by DJ - renamed PostDummyRun to PostRun3, stopped assuming sound check response was a float.
Updated 4/12/19 by DJ - updated to work from command line and with new task version (adding Sound VAS).
"""

# Import packages
import time           # for timing analyses
import numpy as np    # for math
import pandas as pd   # for tables
from matplotlib import pyplot as plt # for plotting
import ast            # for parameter parsing
import re             # for splitting strings
import argparse       # for command-line arguments
from glob import glob # for finding files
import os             # for handling paths

# Import full log (including keypresses)
def ImportExtinctionRecallTaskLog(logFile):
    
    # === Read in PsychoPy log
    
    # Log start
    print('Reading file %s...'%logFile)
    t = time.time()
    
    # Load file
    with open(logFile) as f:
        allLines = f.read().splitlines(True)
    
    # Set up outputs
    dfKey = pd.DataFrame(columns=['t','key'])
    dfDisp = pd.DataFrame(columns=['t','stim','CS'])
    dfSync = pd.DataFrame(columns=['t','value'])
    dfBlock = pd.DataFrame(columns=['tStart','tEnd','type'])
    dfVas = pd.DataFrame(columns=['imageFile','CSplusPercent','type','name','rating','timeToFirstPress','RT','run','group','block','trial','tImage','tStart','tEnd'])
    params = {}
    iKey = 0;
    iDisp = 0;
    iSync = 0;
    iVas = 0;
    iBlock = -1;
    run = 0; # 1-based numbering
    group = 0
    block = 0
    trial = 0
    isParams = False;
    
    # Read each line
    for line in allLines:
        # split into parts
        data = line.split()
    
        # Find params
        if 'START PARAMETERS' in line:
            isParams = True;
        elif 'END PARAMETERS' in line:
            isParams = False;
    
        # Parse params
        elif isParams: # parse parameter
            key = data[2][:-1] # name of parameter
            if len(data)==4:
                try: 
                    params[key] = float(data[3]) # if it's a number, convert to a float
                except ValueError:
                    params[key] = data[3] # otherwise, record the string
            elif data[3].startswith("["):
                params[key] = ast.literal_eval(''.join(data[3:])) # if the parameter is a list, make it a list variable
            else:
                params[key] = ' '.join(data[3:])
    
        # Parse data
        elif len(data)>2:
            if data[2]=='Keypress:': # time and key pressed
                dfKey.loc[iKey,'t'] = float(data[0])
                dfKey.loc[iKey,'key'] = data[3]
                iKey +=1;
            elif data[2]=='Display': # time and stim presented
                dfDisp.loc[iDisp,'t'] = float(data[0])
                dfDisp.loc[iDisp,'stim'] = data[3]
                if len(data)>4: # if a CS level is specified...
                    trial +=1
                    dfDisp.loc[iDisp,'CS'] = data[4] # log it
                    # set VAS stimulus and type
                    dfVas.loc[iVas,'tImage'] = dfDisp.loc[iDisp,'t']
                    dfVas.loc[iVas,'imageFile'] = dfDisp.loc[iDisp,'stim']
                    dfVas.loc[iVas,'CSplusPercent'] = int(dfDisp.loc[iDisp,'CS'][6:])
                    dfVas.loc[iVas,'type'] = dfBlock.loc[iBlock,'type']
                iDisp +=1;
            elif data[2]=='set': # message time and text
                dfSync.loc[iSync,'t'] = float(data[0])
                dfSync.loc[iSync,'value'] = float(data[-1])
                iSync +=1;
            elif data[2]=='=====' and data[3]=='START' and data[4]=='RUN':
                run +=1
            elif data[2]=='====' and data[3]=='START' and data[4]=='GROUP':
                group = int(data[5][0])
            elif data[2]=='===' and data[3]=='START' and data[4]=='BLOCK': # block start time
                block = int(data[5][0])
                trial = 0
                iBlock +=1;
                dfBlock.loc[iBlock,'tStart'] = float(data[0])
            elif data[2]=='bottomMsg:':
                if 'AFRAID' in line:
                    dfBlock.loc[iBlock,'type'] = 'afraid'
                elif 'SCREAM' in line:
                    dfBlock.loc[iBlock,'type'] = 'scream'
            elif data[2]=='Created' and data[3].startswith('Vas'):
                if 'nervous' in line:
                    dfVas.loc[iVas,'type']='nervous'
                elif 'mood right now' in line:
                    dfVas.loc[iVas,'type']='mood'
                elif 'scale=str(...)' in line: # kluge - won't work if multiple types have multi-line text
                    dfVas.loc[iVas,'type']='worried'
            elif data[2]=='RatingScale': # VAS time, rating, RT
                if "rating=" in line:
                    dfVas.loc[iVas,'tStart'] = dfDisp.loc[iDisp-1,'t']
                    dfVas.loc[iVas,'tEnd'] = float(data[0])
                    dfVas.loc[iVas,'name'] = data[3][:-1]
                    value = float(data[-1].split("=")[-1])
                    dfVas.loc[iVas,'rating'] = value
                    # if it's a mood vas, set type
                    if pd.isnull(dfVas.loc[iVas,'type']):
                        dfVas.loc[iVas,'type'] = 'mood'
                    else:
                        dfVas.loc[iVas,'run'] = run
                        dfVas.loc[iVas,'group'] = group
                        dfVas.loc[iVas,'block'] = block
                        dfVas.loc[iVas,'trial'] = trial
                elif "RT=" in line:
                    value = float(data[-1].split("=")[-1])
                    dfVas.loc[iVas,'RT'] = value
                elif "history=" in line:
                    # get time to first button presss
                    if len(re.split('\), |, |\)]',line))>3:
                        timeToPress = float(re.split('\), |, |\)]',line)[3])
                    else:
                        timeToPress = dfVas.loc[iVas,'RT'] # if no press, default to RT
                    dfVas.loc[iVas,'timeToFirstPress'] = timeToPress
                    # increment VAS index
                    iVas +=1;        
    print('Done! Took %.1f seconds.'%(time.time()-t))
    
    
    print('Extracting VAS data...')
    t = time.time()
    # Parse out mood and sound VAS results
    dfMoodVas = dfVas.loc[pd.isnull(dfVas['imageFile']),:]
    dfMoodVas = dfMoodVas.drop(['imageFile','CSplusPercent','run','group','block','trial','tImage'],1)
    # split into mood & sound
    dfSoundVas = dfMoodVas.loc[dfMoodVas.name.str.startswith('SoundCheck'),:]
    dfMoodVas = dfMoodVas.loc[~dfMoodVas.name.str.startswith('SoundCheck'),:]
    # reset indices
    dfSoundVas = dfSoundVas.reset_index(drop=True)
    dfMoodVas = dfMoodVas.reset_index(drop=True)
    
    # Parse out image VAS results
    dfImageVas = dfVas.loc[pd.notnull(dfVas['imageFile']),:]
    dfImageVas = dfImageVas.drop('name',1)

    # add Mood VAS types
    isTraining = 'Training' in logFile
    dfMoodVas = GetVasTypes(params,dfMoodVas,isTraining)
    
    # add Sound VAS types (assuming only one question per sound!!!)
    dfSoundVas['group']=np.arange(dfSoundVas.shape[0]) 
    dfSoundVas['groupName']=[x.split('-')[0] for x in dfSoundVas.name]
    dfSoundVas['type']='loud'
    
    print('Done! Took %.1f seconds.'%(time.time()-t))

    # Return results
    return params, dfMoodVas, dfSoundVas, dfImageVas, dfKey, dfDisp, dfSync, dfBlock



# Import VAS parts of log (excluding keypresses)
def ImportExtinctionRecallTaskLog_VasOnly(logFile):
    
    # === Read in PsychoPy log
    
    # Log start
    print('Reading file %s...'%logFile)
    t = time.time()
    
    # Load file
    with open(logFile) as f:
        allLines = f.read().splitlines(True)
    
    # Set up outputs
    dfDisp = pd.DataFrame(columns=['t','stim','CS'])
    dfBlock = pd.DataFrame(columns=['tStart','tEnd','type'])
    dfVas = pd.DataFrame(columns=['imageFile','CSplusPercent','type','name','rating','timeToFirstPress','RT','run','group','block','trial','tImage','tStart','tEnd'])
    params = {}
    iDisp = 0;
    iVas = 0;
    iBlock = -1;
    run = 0; # 1-based numbering
    group = 0
    block = 0
    trial = 0
    isParams = False;
    
    # Read each line
    for line in allLines:
        # split into parts
        data = line.split()
    
        # Find params
        if 'START PARAMETERS' in line:
            isParams = True;
        elif 'END PARAMETERS' in line:
            isParams = False;
    
        # Parse params
        elif isParams: # parse parameter
            key = data[2][:-1] # name of parameter
            if len(data)==4:
                try: 
                    params[key] = float(data[3]) # if it's a number, convert to a float
                except ValueError:
                    params[key] = data[3] # otherwise, record the string
            elif data[3].startswith("["):
                params[key] = ast.literal_eval(''.join(data[3:])) # if the parameter is a list, make it a list variable
            else:
                params[key] = ' '.join(data[3:])
    
        # Parse data
        elif len(data)>2:
            if data[2]=='Display': # time and stim presented
                dfDisp.loc[iDisp,'t'] = float(data[0])
                dfDisp.loc[iDisp,'stim'] = data[3]
                if len(data)>4: # if a CS level is specified...
                    trial +=1
                    dfDisp.loc[iDisp,'CS'] = data[4] # log it
                    # set VAS stimulus and type
                    dfVas.loc[iVas,'tImage'] = dfDisp.loc[iDisp,'t']
                    dfVas.loc[iVas,'imageFile'] = dfDisp.loc[iDisp,'stim']
                    dfVas.loc[iVas,'CSplusPercent'] = int(dfDisp.loc[iDisp,'CS'][6:])
                    dfVas.loc[iVas,'type'] = dfBlock.loc[iBlock,'type']
                iDisp +=1;
            elif data[2]=='=====' and data[3]=='START' and data[4]=='RUN':
                run +=1
            elif data[2]=='====' and data[3]=='START' and data[4]=='GROUP':
                group = int(data[5][0])
            elif data[2]=='===' and data[3]=='START' and data[4]=='BLOCK': # block start time
                block = int(data[5][0])
                trial = 0
                iBlock +=1;
                dfBlock.loc[iBlock,'tStart'] = float(data[0])
            elif data[2]=='bottomMsg:':
                if 'AFRAID' in line:
                    dfBlock.loc[iBlock,'type'] = 'afraid'
                elif 'SCREAM' in line:
                    dfBlock.loc[iBlock,'type'] = 'scream'
            elif data[2]=='RatingScale': # VAS time, rating, RT
                if "rating=" in line:
                    dfVas.loc[iVas,'tStart'] = dfDisp.loc[iDisp-1,'t']
                    dfVas.loc[iVas,'tEnd'] = float(data[0])
                    dfVas.loc[iVas,'name'] = data[3][:-1]
                    value = float(data[-1].split("=")[-1])
                    dfVas.loc[iVas,'rating'] = value
                    # if it's a mood vas, set type
                    if pd.isnull(dfVas.loc[iVas,'type']):
                        dfVas.loc[iVas,'type'] = 'mood'
                    else:
                        dfVas.loc[iVas,'run'] = run
                        dfVas.loc[iVas,'group'] = group
                        dfVas.loc[iVas,'block'] = block
                        dfVas.loc[iVas,'trial'] = trial
                elif "RT=" in line:
                    value = float(data[-1].split("=")[-1])
                    dfVas.loc[iVas,'RT'] = value
                elif "history=" in line:
                    # get time to first button presss
                    if len(re.split('\), |, |\)]',line))>3:
                        timeToPress = float(re.split('\), |, |\)]',line)[3])
                    else:
                        timeToPress = dfVas.loc[iVas,'RT'] # if no press, default to RT
                    dfVas.loc[iVas,'timeToFirstPress'] = timeToPress
                    # increment VAS index
                    iVas +=1;                 

    
    print('Done! Took %.1f seconds.'%(time.time()-t))
    
    print('Extracting VAS data...')
    t = time.time()
    # Parse out mood and sound VAS results
    dfMoodVas = dfVas.loc[pd.isnull(dfVas['imageFile']),:]
    dfMoodVas = dfMoodVas.drop(['imageFile','CSplusPercent','run','group','block','trial','tImage'],1)
    # split into mood & sound
    dfSoundVas = dfMoodVas.loc[dfMoodVas.name.str.startswith('SoundCheck'),:]
    dfMoodVas = dfMoodVas.loc[~dfMoodVas.name.str.startswith('SoundCheck'),:]
    # reset indices
    dfSoundVas = dfSoundVas.reset_index(drop=True)
    dfMoodVas = dfMoodVas.reset_index(drop=True)
    
    # Parse out image VAS results
    dfImageVas = dfVas.loc[pd.notnull(dfVas['imageFile']),:]
    dfImageVas = dfImageVas.drop('name',1)

    # add Mood VAS types
    isTraining = 'Training' in logFile
    dfMoodVas = GetVasTypes(params,dfMoodVas,isTraining)
    
    # add Sound VAS types (assuming only one question per sound!!!)
    dfSoundVas['group']=np.arange(dfSoundVas.shape[0]) 
    dfSoundVas['groupName']=[x.split('-')[0] for x in dfSoundVas.name]
    dfSoundVas['type']='loud'
    
    print('Done! Took %.1f seconds.'%(time.time()-t))

    # Return results
    return params, dfMoodVas, dfSoundVas, dfImageVas


# Add accurate group, groupName, and type columns to the dfMoodVas dataframe 
def GetVasTypes(params,dfMoodVas,isTraining=False):
    
    # declare constants
    if isTraining:
        vasGroups = ['PreRun1']
    else:
        vasGroups = ['PreSoundCheck','PostRun1','PostRun2','PostRun3']
    magicWords = ['anxious','tired','worried are','mood','doing','feared']
    
    # check each group file for magic words
    for i,groupName in enumerate(vasGroups):
        try:
            vasFile = params['moodQuestionFile%d'%(i+1)]
            print('reading %s...'%vasFile)
            # read file to get list of questions
            with open(vasFile,"r") as fi:
                questions = []
                for ln in fi:
                    if ln.startswith("?"):
                        questions.append(ln[1:])
                
            for j,question in enumerate(questions):
                isThis = dfMoodVas.name=='%s-%d'%(groupName,j)
                dfMoodVas.loc[isThis,'group'] = i
                dfMoodVas.loc[isThis,'groupName'] = groupName
                for k,word in enumerate(magicWords):
                    if word in question:
                        dfMoodVas.loc[isThis,'type'] = word.split()[0]
        except:
            print('group %s not found.'%groupName)
            
    return dfMoodVas # return modified dataframe

# Save figures of the image and mood VAS responses and RTs.
def SaveVasFigures(params,dfMoodVas,dfSoundVas,dfImageVas,outPrefix='ER3_'):

    # Set up
    outBase = os.path.basename(outPrefix) # filename without the folder
    print('Plotting VAS data...')
    t = time.time()
    
    # === MOOD VAS === #
    # Set up figure
    moodFig = plt.figure(figsize=(8, 4), dpi=120, facecolor='w', edgecolor='k')
    # Plot Ratings
    plt.subplot(121)
    # declare constants
    if 'Training' in outPrefix:
        vasGroups=['PreRun1']
    else:
        vasGroups = ['PreSoundCheck','PostRun1','PostRun2','PostRun3'] 
    vasTypes = ['anxious','tired','worried','mood','doing','feared']
#    vasTypes = dfMoodVas.type.unique()
    
    for vasType in vasTypes:
        isInType = dfMoodVas.type==vasType
        plt.plot(dfMoodVas.loc[isInType,'group'],dfMoodVas.loc[isInType,'rating'],'.-',label=vasType)
    plt.legend()
    plt.xticks(range(len(vasGroups)),vasGroups)
    plt.ylim([0,100])
    plt.xticks(rotation=15)
    plt.xlabel('group')
    plt.ylabel('rating (0-100)')
    plt.title('%s%d-%d\n Mood VAS Ratings'%(outBase,params['subject'],params['session']))
    
    # Plot Reaction Times
    plt.subplot(122)
    for vasType in vasTypes:
        isInType = dfMoodVas.type==vasType
        plt.plot(dfMoodVas.loc[isInType,'group'],dfMoodVas.loc[isInType,'RT'],'.-',label=vasType)
    plt.legend()
    plt.xticks(range(len(vasGroups)),vasGroups)
    plt.xticks(rotation=15)
    plt.xlabel('group')
    plt.ylabel('reaction time (s))')
    plt.title('%s%d-%d\n Mood VAS RTs'%(outBase,params['subject'],params['session']))
    
    # Save figure
    outFile = '%s%d-%d_MoodVasFigure.png'%(outPrefix,params['subject'],params['session'])
    print("Saving Mood VAS figure as %s..."%outFile)
    moodFig.savefig(outFile)
    
    
    
    # === SOUND CHECK VAS === #
    # No sound checks in training task
    if not 'Training' in outPrefix:
        # declare constants
        vasGroups = ['SoundCheck1','SoundCheck2','SoundCheck3'] 
        vasTypes = ['loud']

        # Set up figure
        soundFig = plt.figure(figsize=(8, 4), dpi=120, facecolor='w', edgecolor='k')
        # Plot Ratings
        plt.subplot(121)
        
        for vasType in vasTypes:
            isInType = dfSoundVas.type==vasType
            plt.plot(dfSoundVas.loc[isInType,'group'],dfSoundVas.loc[isInType,'rating'],'.-',label=vasType)
        plt.legend()
        plt.xticks(range(len(vasGroups)),vasGroups)
        plt.ylim([0,100])
        plt.xticks(rotation=15)
        plt.xlabel('group')
        plt.ylabel('rating (0-100)')
        plt.title('%s subject %d session %d\n Sound VAS Ratings'%(outBase,params['subject'],params['session']))
        
        # Plot Reaction Times
        plt.subplot(122)
        for vasType in vasTypes:
            isInType = dfSoundVas.type==vasType
            plt.plot(dfSoundVas.loc[isInType,'group'],dfSoundVas.loc[isInType,'RT'],'.-',label=vasType)
        plt.legend()
        plt.xticks(range(len(vasGroups)),vasGroups)
        plt.xticks(rotation=15)
        plt.xlabel('group')
        plt.ylabel('reaction time (s))')
        plt.title('%s subject %d session %d\n Sound VAS RTs'%(outBase,params['subject'],params['session']))
    
        # Save figure
        outFile = '%s%d-%d_SoundVasFigure.png'%(outPrefix,params['subject'],params['session'])
        print("Saving Sound VAS figure as %s..."%outFile)
        soundFig.savefig(outFile)
    
    # === IMAGE VAS === #
    # Plot image VAS results
    imgFig = plt.figure(figsize=(8, 4), dpi=120, facecolor='w', edgecolor='k')
    
    # Plot Ratings
    plt.subplot(121)
    vasTypes = dfImageVas.type.unique()
    for vasType in vasTypes:
        isInType = dfImageVas.type==vasType
        plt.plot(dfImageVas.loc[isInType,'CSplusPercent'],dfImageVas.loc[isInType,'rating'],'.',label=vasType)
    plt.legend()
    plt.ylim([0,100])
    plt.xticks(rotation=15)
    plt.xlabel('CS plus level (%)')
    plt.ylabel('rating (0-100)')
    plt.title('%s%d-%d\n Image VAS Ratings'%(outBase,params['subject'],params['session']))
    
    # Plot Reaction Times
    plt.subplot(122)
    for vasType in vasTypes:
        isInType = dfImageVas.type==vasType
        plt.plot(dfImageVas.loc[isInType,'CSplusPercent'],dfImageVas.loc[isInType,'RT'],'.',label=vasType)
    plt.legend()
    plt.xticks(rotation=15)
    plt.xlabel('CS plus level (%)')
    plt.ylabel('reaction time (s))')
    plt.title('%s%d-%d\n Image VAS RTs'%(outBase,params['subject'],params['session']))

    # Save figure
    outFile = '%s%d-%d_ImageVasFigure.png'%(outPrefix,params['subject'],params['session'])
    print("Saving Image VAS figure as %s..."%outFile)
    imgFig.savefig(outFile)
    
    print('Done! Took %.1f seconds.'%(time.time()-t))


# Convert mood VAS to a single line for logging to multi-subject spreadsheet
def GetSingleVasLine(params,dfVas,isTraining=False,isSoundVas=False):

    
    # === Convert table to single line
    # Declare names of VAS groups/types-within-groups (to be used in legends/tables)
    if isTraining:
        vasGroups = ['PreRun1']
    else:
        if isSoundVas:
            vasGroups = ['SoundCheck1','SoundCheck2','SoundCheck3']
        else:
            vasGroups = ['PreSoundCheck','PostRun1','PostRun2','PostRun3'] # shorthand for each VAS group based on their position in the task
    if isSoundVas:
        vasTypes = ['loud']
    else:
        vasTypes = ['anxious','tired','worried','mood','doing','feared'] # shorthand for VAS0, VAS1, VAS2, etc.
    
    # Convert
    cols = ['subject','session','date']
    for vasGroup in vasGroups:
        for vasType in vasTypes:
            cols = cols + ['%s_%s_rating'%(vasGroup,vasType)]
    for vasGroup in vasGroups:
        for vasType in vasTypes:
            cols = cols + ['%s_%s_RT'%(vasGroup,vasType)]
    # create dataframe
    dfVas_singleRow = pd.DataFrame(columns=cols)
    dfVas_singleRow.subject = dfVas_singleRow.subject.astype(int) # convert SDAN to integer
    # dfVas_singleRow = dfVas_singleRow.set_index('subject') # set SDAN as index
    dfVas_singleRow.loc[0,'subject'] = int(params['subject']) 
    dfVas_singleRow.loc[0,'session'] = int(params['session']) 
    dfVas_singleRow.loc[0,'date'] = params['date']
    
    # Fill out single row
    for vasGroup in vasGroups:
        for vasType in vasTypes:
            isThis = np.logical_and(dfVas.groupName==vasGroup, dfVas.type==vasType)
            if np.any(isThis):
                dfVas_singleRow.loc[0,'%s_%s_rating'%(vasGroup,vasType)] = dfVas.loc[isThis,'rating'].values[0]
                dfVas_singleRow.loc[0,'%s_%s_RT'%(vasGroup,vasType)] = dfVas.loc[isThis,'RT'].values[0]
    
    return dfVas_singleRow


# Do everything: import the log, produce the figures, and produce the tables.
def ProcessERLog(logFilename,outFolder):
    
    # import data
    readParams,dfMoodVas,dfSoundVas,dfImageVas = ImportExtinctionRecallTaskLog_VasOnly(logFilename)

    # create output folder if it doesn't exist
    subjOutFolder = os.path.join(outFolder,'%d'%(readParams['subject']))
    if not os.path.exists(subjOutFolder):
        os.makedirs(subjOutFolder)
    isTraining = ('Training' in logFilename) # is it a training run?
    
    # declare cross-subject table filenames
    if isTraining: # if it's a training run
        outMoodTable = os.path.join(outFolder,'ER3Training-MoodVasTable.xlsx')
        subjOutPrefix = os.path.join(subjOutFolder,'ER3Training_')
    else:
        outMoodTable = os.path.join(outFolder,'ER3-MoodVasTable.xlsx')
        outSoundTable = os.path.join(outFolder,'ER3-SoundVasTable.xlsx')
        subjOutPrefix = os.path.join(subjOutFolder,'ER3_')
    
    # make figures    
    SaveVasFigures(readParams,dfMoodVas,dfSoundVas,dfImageVas,subjOutPrefix)
    
    # convert mood VAS to single line
    dfMoodVas_singleRow = GetSingleVasLine(readParams,dfMoodVas,isTraining)
    # Append output table to file
    print("Appending to Mood VAS table %s..."%os.path.basename(outMoodTable))
    if os.path.exists(outMoodTable):
        dfMoodVas_all = pd.read_excel(outMoodTable,index_col=None)
        dfMoodVas_all = dfMoodVas_all.append(dfMoodVas_singleRow)
        dfMoodVas_all = dfMoodVas_all.drop_duplicates()
        dfMoodVas_all.to_excel(outMoodTable,index=False)
    else:
        dfMoodVas_singleRow.to_excel(outMoodTable,index=False)
        
    if not isTraining: # if it's not a training run
        # convert sound VAS to single line
        dfSoundVas_singleRow = GetSingleVasLine(readParams,dfSoundVas,isTraining,isSoundVas=True)
        # Append output table to file
        print("Appending to Sound VAS table %s..."%os.path.basename(outSoundTable))
        if os.path.exists(outSoundTable):
            dfSoundVas_all = pd.read_excel(outSoundTable,index_col=None)
            dfSoundVas_all = dfSoundVas_all.append(dfSoundVas_singleRow)
            dfSoundVas_all = dfSoundVas_all.drop_duplicates()
            dfSoundVas_all.to_excel(outSoundTable,index=False)
        else:
            dfSoundVas_singleRow.to_excel(outSoundTable,index=False)
        
        
    # Save Image VAS table (one per run)
    runs = dfImageVas.run.unique()
    for run in runs:
        dfImageVas_thisrun = dfImageVas.loc[dfImageVas.run==run,:]
        outImageTable = '%s%d-%d_run%d-ImageVasTable.xlsx'%(subjOutPrefix,readParams['subject'],readParams['session'],run)
        print("Saving Image VAS table %s..."%os.path.basename(outImageTable))
        dfImageVas_thisrun.to_excel(outImageTable,index=False)
    
    print('Done!')




# %% === Set up argument parser === 
    
parser = argparse.ArgumentParser(description='Process ExtinctionRecall3 log file, producing figures and tables with relevant info.')

parser.add_argument('--subjects', nargs='*', default='', help='SDAN numbers of subjects to process')
#parser.add_argument('--logFiles', nargs='*', default='', help='log filename')
parser.add_argument('--isMac', action='store_true', help='use mac paths instead of PC')


# ==== Declare main command-line function ==== #

if __name__ == '__main__':
    
    # parse inputs
    args = parser.parse_args();
    # Get paths to mood vas and sound tables
    if args.isMac:
        baseDir = '/Volumes/sdan1/Data/conditioning/ExtinctionRecall3/Data'
    else:
        baseDir = 'Z:/Data/conditioning/ExtinctionRecall3/Data'
        
    outFolder = os.path.join(baseDir,'Processed')    
    
    for subj in args.subjects:        
        logFiles = glob(os.path.join(baseDir,'Raw','ER3*_%s-*.log'%subj))
        print('Found %d files for subject %s.'%(len(logFiles),subj))
        
        for logFile in logFiles:            
            print('Found file %s...'%logFile)
            ProcessERLog(logFile,outFolder)

        
    
        