# ********************************************************************************;
#  _____              __          __   _            __  __             
# |  __ \             \ \        / /  | |          |  \/  |            
# | |  | | ___  ___ _ _\ \  /\  / /_ _| |_ ___ _ __| \  / | ___  _ __  
# | |  | |/ _ \/ _ \ '_ \ \/  \/ / _` | __/ _ \ '__| |\/| |/ _ \| '_ \ 
# | |__| |  __/  __/ |_) \  /\  / (_| | ||  __/ |  | |  | | (_) | | | |
# |_____/ \___|\___| .__/ \/  \/ \__,_|\__\___|_|  |_|  |_|\___/|_| |_|
#                  | |                                                 
#                  |_|    
#
# Project           : Master thesis - DeepWaterMon
# Program name      : sim.py
# School            : HEIA-FR
# Author            : Lucien Aymon
# Date created      : 07.01.2019
# Purpose           : Run Epanet simulations, result are save on a CSV file, epabstract.py use this script to avoid the
#                       limitation on the maximum simulation permits with Epanettools
# Revision History  :
# Date        Author      Ref    Revision
# 
# Input: Filepath (str), path to INP file, path to result (CSV file)
# Output: Network summary
# ********************************************************************************;

# -----------------------------------------
# Import
# -----------------------------------------
import epanettools.epanettools as epa
import sys
import csv

# ------------------------------------
# Constants
# ------------------------------------
CANNES_ID_FILES = sys.argv[3]
id_cannes = []

# ------------------------------------
# Read points of consumption
# ------------------------------------
def readPCID():
    with open(CANNES_ID_FILES, 'r') as f:
        reader = csv.reader(f)
        raw_list = list(reader)
        id_cannes_read = [int(item) for sublist in raw_list for item in sublist]
    for i in id_cannes_read:
        id_cannes.append(i)

# -----------------------------------------
# Unit converter
# -----------------------------------------
def convertUnit(type, val):
    if type is "pressure":
        return val * 0.098064           # Convert [H2O m] to [bar]
    else:
        if type is "flow":
            return val * 264 * 60       # [m3/s] to gallon per minute [GPM]
        else:
            return val

# -----------------------------------------
# Run simulation and save result in CSV
# -----------------------------------------
def runSim():
    if len(sys.argv) is not 5:
        return -1
    else:
        readPCID()
        es=epa.EPANetSimulation(sys.argv[1])
        es.run()
        p=epa.Node.value_type['EN_PRESSURE']
        d=epa.Node.value_type['EN_DEMAND']
        f_result = open(sys.argv[2], 'w')
        pre = {}
        for key, value in es.network.nodes.items():
            # Only save pressure and flow for real equipement
            if int(value.id) in id_cannes:
                # Tag the closest node of the leak
                if sys.argv[4] is not 0:
                    if int(value.id) is int(sys.argv[4]):
                        f_result.write(value.id + "," + str(convertUnit("pressure", value.results[p][0])) + "," + '1' + "\n")
                    else:
                        f_result.write(value.id + "," + str(convertUnit("pressure", value.results[p][0])) + "," + '0' + "\n")
                else:
                    f_result.write(value.id + "," + str(convertUnit("pressure", value.results[p][0])) + "," + str(convertUnit("flow", value.results[d][0])) + "\n")
                pre[value.id] = str(convertUnit("pressure", value.results[p][0]))
        f_result.close()

# -----------------------------------------
# Main
# ----------------------------------------
if __name__ == '__main__':
    runSim()