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
# Program name      : epabstract.py
# School            : HEIA-FR
# Author            : Lucien Aymon
# Date created      : 23.10.2018
# Purpose           : Parse an Epanet file (INP) to create Epanet obects and simulate
#                       the network with Epanet
# Revision History  :
# Date        Author      Ref    Revision
# 
# Input: Filepath (str)
# Output: Network summary
# ********************************************************************************;

# ------------------------------------
# Import
# ------------------------------------
import ast
import csv
import datetime
import importlib
import ntpath
import os
import random
import re
import sys
import time
from shutil import copyfile

import epanettools.epanettools as epa
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d import Axes3D
from numpy.polynomial.polynomial import polyfit
from prettytable import PrettyTable
from pushbullet import Pushbullet

# ------------------------------------
# Constants
# ------------------------------------
PATH = sys.argv[1]
CANNES_ID_FILES = sys.argv[2]
SIM_RATIO = int(sys.argv[3])
LEAK = sys.argv[4]
RESULT_PATH = "results/dataset_{0}_{1}_{2}.csv".format(ntpath.basename(PATH), SIM_RATIO, LEAK)
DEBUG = 0
COLOR_3D_TXT = 1
JUNCTION_INFO_SIZE = 4
RESERVOIR_INFO_SIZE = 3
TANK_INFO_SIZE = 8
PIPE_INFO_SIZE = 8
PUMP_INFO_SIZE = 8
VALVE_INFO_SIZE = 8
PUSHBULLET_API_KEY = "o.OMvCwTQLnDzXBIHJvV5uvpPjj4a70rnc"

# ------------------------------------
# Epanet Class
# ------------------------------------
# -- EpanetFile --
class EpanetFile:
    def __init__(self, title, path, result_path):
            self.title = title
            self.path = path
            self.junctions = {}
            self.reservoirs = {}
            self.tanks = {}
            self.pipes = {}
            self.pumps = {}
            self.valves = {}
            self.pipes_sim = []
            self.max_x = 0.0
            self.max_y = 0.0
            self.id_cannes = []
            self.result_path = result_path
            self.sim_cnt = 0
    
    # ------------------------------------
    # Simulation method
    # ------------------------------------
    def sim_data(self):
        first = 1
        s = datetime.datetime.now()
        s_nbr = len(self.pipes) * SIM_RATIO
        print("Starting {0} simulations at {1}".format(s_nbr, s))
        for i in range(s_nbr):
            reset()
            if LEAK == "rand":
                node = addLeaksMiddle(convertUnit("flow", random.randint(1, 10)/3600), random.randint(5, 95)/100, 1)
            else:
                node = addLeaksMiddle(convertUnit("flow", 2/3600), random.randint(5, 95)/100, 1)
            sim(node, first)
            first += 1
        f = datetime.datetime.now()
        sim_msg = "Simulations finished in {0}".format(f-s)
        print(sim_msg)
        # Sending the notification
        push = pb.push_note("WaterMon sim {0}_{1}_{2}".format(ntpath.basename(PATH), SIM_RATIO, LEAK), sim_msg)
        # Histogram of the simulated pipes
        bins = np.arange(0, Pipe.id_max, 1)
        n, bin, patches = plt.hist(ef.pipes_sim, bins=bins, facecolor='g', alpha=0.75)
        plt.xlabel('Pipes')
        plt.ylabel('Simulations')
        plt.title('Histogram of simulated pipes')
        plt.grid(True)

# -- Junction --
class Junction:
    id_max = 0
    def __init__(self, id, elevation, demand, pattern, posX, posY, ec):
            self.id = id
            self.elevation = int(elevation)
            self.demand = int(demand)
            self.pattern = pattern
            self.posX = float(posX)
            self.posY = float(posY)
            self.ec = int(ec)
            self.pressure = 0
            if int(id) > Pipe.id_max:
                Junction.id_max = int(id)

    def __str__(self):
        return "-- Junctions {} --\nPosition X: {}, Y: {}\nEmitter coefficient: {}, Demand: {}\n".format(self.id, self.posX, self.posY, self.ec, self.demand)

# -- Pipe --
class Pipe:
    id_max = 0
    def __init__(self, id, node1, node2, length, diameter, roughness, minorLoss, status):
            self.id = int(id)
            self.node1 = node1
            self.node2 = node2
            self.length = float(length)
            self.diameter = diameter
            self.roughness = roughness
            self.minorLoss = minorLoss
            self.status = status
            if int(id) > Pipe.id_max:
                Pipe.id_max = int(id)
            
    def __str__(self):
        return "-- Pipe {} --\nNode 1: {}, 2: {}\nStatus: {}\n".format(self.id, self.node1, self.node2, self.status)

# -- Valve --
class Valve:
    def __init__(self, id, node1, node2, diameter, type, setting, minorLoss, status):
            self.id = id
            self.node1 = node1
            self.node2 = node2
            self.diameter = diameter
            self.type = type
            self.setting = setting
            self.minorLoss = minorLoss
            self.status = status

# -- Pump --
class Pump:
    def __init__(self, id, node1, node2, parameters):
            self.id = id
            self.node1 = node1
            self.node2 = node2
            self.parameters = parameters

# -- Reservoir --
class Reservoir:
    def __init__(self, id, head, pattern):
            self.id = id
            self.head = head
            self.pattern = pattern

# -- Tank --
class Tank:
    def __init__(self, id, elevation, initLevel, minLevel, maxLevel, diameter, minVol, volCurve):
            self.id = id
            self.elevation = elevation
            self.initLevel = initLevel
            self.minLevel = minLevel
            self.maxLevel = maxLevel
            self.diameter = diameter
            self.minVol = minVol
            self.volCurve = volCurve

# ------------------------------------
# Global variables
# ------------------------------------
start_time = 0
ef = EpanetFile("", PATH, RESULT_PATH)
state = 0
pb = Pushbullet(PUSHBULLET_API_KEY)
state_d = {}
state_d["TITLE"] = 1
state_d["JUNCTIONS"] = 2
state_d["PIPES"] = 3
state_d["VALVES"] = 4
state_d["PUMPS"] = 5
state_d["RESERVOIRS"] = 6
state_d["TANKS"] = 7
state_d["COORDINATES"] = 8
state_d["EMITTERS"] = 9
state_d["STATUS"] = 10
state_d["PATTERNS"] = 11
state_d["DEMANDS"] = 12
green_3d = [83, 64, 76, 71, 77, 74, 65, 70, 69, 62]
red_3d = [14, 15, 4, 20, 8, 5, 12, 9, 6, 10]

# ------------------------------------
# Tag detection
# ------------------------------------
def getTitle(line):
    _title = re.compile(r'(^\[TITLE\])\s*([^\[]*)')
    if _title.match(line):
        return state_d["TITLE"]

def getJunction(line):
    _junction = re.compile(r'(^\[JUNCTIONS\])\s*([^\[]*)')
    if _junction.match(line):
       return state_d["JUNCTIONS"]

def getPipe(line):
    _pipe = re.compile(r'(^\[PIPES\])\s*([^\[]*)')
    if _pipe.match(line):
        return state_d["PIPES"]

def getValve(line):
    _valve = re.compile(r'(^\[VALVES\])\s*([^\[]*)')
    if _valve.match(line):
        return state_d["VALVES"]

def getPump(line):
    _pump = re.compile(r'(^\[PUMPS\])\s*([^\[]*)')
    if _pump.match(line):
        return state_d["PUMPS"]

def getReservoir(line):
    _reservoir = re.compile(r'(^\[RESERVOIRS\])\s*([^\[]*)')
    if _reservoir.match(line):
        return state_d["RESERVOIRS"]

def getTank(line):
    _tank = re.compile(r'(^\[TANKS\])\s*([^\[]*)')
    if _tank.match(line):
        return state_d["TANKS"]
    
def getCoordinate(line):
    _coordinate = re.compile(r'(^\[COORDINATES\])\s*([^\[]*)')
    if _coordinate.match(line):
        return state_d["COORDINATES"]

def getEmitter(line):
    _emitter = re.compile(r'(^\[EMITTERS\])\s*([^\[]*)')
    if _emitter.match(line):
        return state_d["EMITTERS"]

def getStatus(line):
    _status = re.compile(r'(^\[STATUS\])\s*([^\[]*)')
    if _status.match(line):
        return state_d["STATUS"]

def getPattern(line):
    _pattern = re.compile(r'(^\[PATTERNS\])\s*([^\[]*)')
    if _pattern.match(line):
        return state_d["PATTERNS"]

def getDemands(line):
    _demand = re.compile(r'(^\[DEMANDS\])\s*([^\[]*)')
    if _demand.match(line):
        return state_d["DEMANDS"]

def detectTag(line):
    _tag = re.compile(r'(^\[)\s*([^\[]*)')
    if _tag.match(line):
        return 1
    else:
        return None

# ------------------------------------
# End detection
# ------------------------------------
def getEnd(line):
    _demand = re.compile(r'(^\[END\])\s*([^\[]*)')
    if _demand.match(line):
        sys.exit(0)

# ------------------------------------
# Save title
# ------------------------------------
def saveTitle():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        while line:
            if getTitle(line) == state_d["TITLE"]:
                line = next(file, None)
                ef.title = line[:-1] # Without the \n
                break
            line = next(file, None)

# ------------------------------------
# Save junctions
# ------------------------------------
def saveJunctions():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        junctionsPart = 0
        while line:
            s = getJunction(line)
            if s == state_d["JUNCTIONS"]:
                junctionsPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and junctionsPart is not 0:
                return 0
            if junctionsPart and len(line.split()):
                ls = line.split()
                size = len(ls) - 1
                if size < JUNCTION_INFO_SIZE:
                    for j in range(size, JUNCTION_INFO_SIZE-1):
                        ls[j] = ""
                j = Junction(ls[0], ls[1], ls[2], "", 0, 0, 0)
                ef.junctions[j.id] = j
            line = next(file, None)

# ------------------------------------
# Save reservoirs
# ------------------------------------
def saveReservoirs():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        reservoirsPart = 0
        while line:
            s = getReservoir(line)
            if s == state_d["RESERVOIRS"]:
                reservoirsPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and reservoirsPart is not 0:
                return 0
            if reservoirsPart and len(line.split()):
                ls = line.split()
                size = len(ls) - 1
                if size < RESERVOIR_INFO_SIZE:
                    for j in range(size, RESERVOIR_INFO_SIZE-1):
                        ls[j] = ""
                j = Reservoir(ls[0], ls[1], ls[2])
                ef.reservoirs[j.id] = j
            line = next(file, None)

# ------------------------------------
# Save tanks
# ------------------------------------
def saveTanks():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        tanksPart = 0
        while line:
            s = getTank(line)
            if s == state_d["TANKS"]:
                tanksPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and tanksPart is not 0:
                return 0
            if tanksPart and len(line.split()):
                ls = line.split()
                size = len(ls) - 1
                if size < TANK_INFO_SIZE:
                    for j in range(size, TANK_INFO_SIZE-1):
                        ls[j] = ""
                j = Tank(ls[0], ls[1], ls[2], ls[3], ls[4], ls[5], ls[6], ls[7])
                ef.tanks[j.id] = j
            line = next(file, None)


# ------------------------------------
# Save pipes
# ------------------------------------
def savePipes():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        pipesPart = 0
        while line:
            s = getPipe(line)
            if s == state_d["PIPES"]:
                pipesPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and pipesPart is not 0:
                return 0
            if pipesPart and len(line.split()):
                ls = line.split()
                size = len(ls) - 1
                if size < PIPE_INFO_SIZE:
                    for j in range(size, PIPE_INFO_SIZE-1):
                        ls[j] = ""
                j = Pipe(ls[0], ls[1], ls[2], ls[3], ls[4], ls[5], ls[6], ls[7])
                ef.pipes[j.id] = j
            line = next(file, None)


# ------------------------------------
# Save pumps
# ------------------------------------
def savePumps():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        pumpsPart = 0
        while line:
            s = getJunction(line)
            if s == state_d["PUMPS"]:
                pumpsPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and pumpsPart is not 0:
                return 0
            if pumpsPart and len(line.split()):
                ls = line.split()
                size = len(ls) - 1
                if size < PUMP_INFO_SIZE:
                    for j in range(size, PUMP_INFO_SIZE-1):
                        ls[j] = ""
                j = Pumps(ls[0], ls[1], ls[2], ls[3])
                ef.pumps[j.id] = j
            line = next(file, None)

# ------------------------------------
# Save valves
# ------------------------------------
def saveValves():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        valvesPart = 0
        while line:
            s = getValve(line)
            if s == state_d["VALVES"]:
                valvesPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and valvesPart is not 0:
                return 0
            if valvesPart and len(line.split()):
                ls = line.split()
                size = len(ls) - 1
                if size < VALVE_INFO_SIZE:
                    for j in range(size, VALVE_INFO_SIZE-1):
                        ls[j] = ""
                j = Valve(ls[0], ls[1], ls[2], ls[3], ls[4], ls[5], ls[6], "")
                ef.valves[j.id] = j
            line = next(file, None)

# ------------------------------------
# Save coordinates
# ------------------------------------
def saveCoordinates():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        coordinatesPart = 0
        while line:
            s = getCoordinate(line)
            if s == state_d["COORDINATES"]:
                coordinatesPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and coordinatesPart is not 0:
                return 0
            if coordinatesPart and len(line.split()):
                ls = line.split()
                if ls[0] in ef.junctions:
                    ef.junctions[ls[0]].posX = ls[1]
                    ef.junctions[ls[0]].posY = ls[2]
                    if float(ls[1]) > float(ef.max_x):
                        ef.max_x = ls[1]
                    if float(ls[2]) > float(ef.max_y):
                        ef.max_y = ls[2]
            line = next(file, None)

# ------------------------------------
# Save status
# ------------------------------------
def saveStatus():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        statusPart = 0
        while line:
            s = getStatus(line)
            if s == state_d["STATUS"]:
                statusPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and statusPart is not 0:
                return 0
            if statusPart and len(line.split()):
                ls = line.split()
                if ls[0] in ef.valves:
                    ef.valves[ls[0]].status = ls[1]
            line = next(file, None)

# ------------------------------------
# Save emitter coefficient
# ------------------------------------
def saveEmitters():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        emitterPart = 0
        while line:
            s = getEmitter(line)
            if s == state_d["EMITTERS"]:
                emitterPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and emitterPart is not 0:
                return 0
            if emitterPart and len(line.split()):
                ls = line.split()
                if ls[0] in ef.junctions:
                    ef.junctions[ls[0]].ec = ls[1]
            line = next(file, None)

# ------------------------------------
# Save demand
# ------------------------------------
def saveDemands():
    with open(ef.path, 'r') as file:
        line = next(file, None)
        demandPart = 0
        while line:
            s = getDemands(line)
            if s == state_d["DEMANDS"]:
                demandPart = 1
                line = next(file, None)
                line = next(file, None) # Remove header line
            if detectTag(line) is not None and demandPart is not 0:
                return 0
            if demandPart and len(line.split()):
                ls = line.split()
                if ls[0] in ef.junctions:
                    ef.junctions[ls[0]].demand = ls[1]
            line = next(file, None)
# ----------------------------------------------
# Print the table of pressure
# ----------------------------------------------
def printPressure():
    t = ["ID opened"]
    for key, value in ef.junctions.items():
        if int(value.id) in ef.id_cannes:
            t.append(value.id)
    prt = PrettyTable(t)
    tbl_html = ""
    row = ""
    col = []
    tbl_html += "["
    row_index = "['"
    line_index = "['"
    for key, value in ef.junctions.items():
        col.append(value.id)
        sys.stdout.write("[" + value.id + "] ")
        sys.stdout.flush()
        if int(value.id) in ef.id_cannes:
            writeBD(value.id, 10)
            line_index += "Open: " + value.id + "', '"
            row_index += value.id + "', '"
            row = "["
            for key_r, value_r in ef.junctions.items():
                if int(value_r.id) in ef.id_cannes:
                    row += "%.2f" % convertUnit("pressure", value_r.pressure) + ", "
            row = row[:-2] + "]"
            tbl_html += row + ", "
    row_index = row_index[:-3] + "]"
    line_index = line_index[:-3] + "]"
    tbl_html = tbl_html[:-2] + "]"
    data = np.array(ast.literal_eval(tbl_html))
    data_index = data[0:,0]
    data_f = pd.DataFrame(data=data, index=ast.literal_eval(line_index), columns=ast.literal_eval(row_index))
    f = open("results/tbl_open.html", 'w')
    min = 1
    x_min = ""
    y_min = ""
    for i in ast.literal_eval(row_index):
        if len(data_f[i].idxmin().split()) >= 2:
            if int(data_f[i].idxmin().split()[1]) is not int(i):
                if data_f[i][data_f[i].idxmin()] < min and data_f[i].idxmin() is not ("Opened: " + i):
                    min = data_f[i][data_f[i].idxmin()]
                    x_min = data_f[i].idxmin()
                    y_min = i
    f.write("Pressure on junction " + str(y_min) + " with " + str(x_min.split()[1]) + " open is minimum on the network with <strong>" + str(min) + " [Pa]</strong><br />")
    f.write("Simulation for a null pressure on junction " + str(y_min) + " with " + str(x_min.split()[1]) + " open")
    f.write(data_f.to_html())
    f.close()
    print("\nArray of pressure exported")

# ------------------------------------
# Draw the junctions
# ------------------------------------
def drawNetwork(type):
    if type is "EC":
        graph = ""
        print("Position X max: ", ef.max_x)
        print("Position Y max: ", ef.max_y)
        ratio_x = 125/float(ef.max_x)
        ratio_y = 75/float(ef.max_y)
        a = np.zeros(shape=(125,75))
        for key, value in ef.junctions.items():
            x = int(float(value.posX)*ratio_x)-1
            y = int(float(value.posY)*ratio_y)-1
            if value.ec is not 0:
                a[x][y] = float(value.ec)
            else:
                a[x][y] = 158 # Random number, too big for a real EC

        for i in range(0, 75):
            for j in range(0, 125):
                if a[j][74-i]:
                    if int(a[j][74-i])-158 is not 0:
                        graph = graph + "@"
                    else:
                        graph = graph + "X"
                else:
                    graph = graph + " "
            graph = graph + "\n"
        return graph
    if type is "PC":
        graph = ""
        print("Position X max: ", ef.max_x)
        print("Position Y max: ", ef.max_y)
        ratio_x = 125/float(ef.max_x)
        ratio_y = 75/float(ef.max_y)
        a = np.zeros(shape=(125,75))
        for key, value in ef.junctions.items():
            x = int(float(value.posX)*ratio_x)-1
            y = int(float(value.posY)*ratio_y)-1
            a[x][y] = value.id
        for i in range(0, 75):
            for j in range(0, 125):
                if not a[j][74-i]:
                    graph = graph + " "
                else:
                    if int(a[j][74-i]) in ef.id_cannes:
                        graph = graph + u"\u2580"
                    else:
                        graph = graph + u"\u2592"
            graph = graph + "\n"
        return graph

# ------------------------------------
# Read points of consumption
# ------------------------------------
def readPCID():
    if not ef.id_cannes:
        with open(CANNES_ID_FILES, 'r') as f:
            reader = csv.reader(f)
            raw_list = list(reader)
            id_cannes = [int(item) for sublist in raw_list for item in sublist]
        for i in id_cannes:
            ef.id_cannes.append(i)

# ------------------------------------
# Write new base demand on junction
# ------------------------------------
def writeBD(junctions, demand, save=0):
    demand = int(demand)
    f_epanet = open(ef.path, 'r')
    lines = f_epanet.readlines()
    f_epanet.close()

    if junctions is 0 and demand is 0:
        es=epa.EPANetSimulation(ef.path)
        es.run()
        p=epa.Node.value_type['EN_PRESSURE']
        pre = {}
        for key, value in es.network.nodes.items():
            pre[value.id] = value.results[p][0]
        for key, value in ef.junctions.items():
            ef.junctions[key].pressure = pre[value.id]
    else:
        file_name = "sim_{0}_{1}_{2}.inp".format(ntpath.basename(PATH), SIM_RATIO, LEAK)
        junctionsPart = 0
        f_epa = open("networks/" + file_name, 'w')
        for line in lines:
            s = getJunction(line)
            if junctionsPart is 2:
                if detectTag(line):
                    junctionsPart = 0
                ls = line.split()
                if len(ls) > 3:
                    if int(ls[0]) in junctions:
                        line = " " + str(ls[0]) + "              	" + str(ls[1]) + "         	" + str(demand)  + "              	" + "              	" + ";\n"
            if junctionsPart is 1:
                junctionsPart = 2   
            if s == state_d["JUNCTIONS"]:
                junctionsPart = 1
            f_epa.write(line)
        f_epa.close()
        # Simulation with Epanet
        epaFile = "networks/" + file_name
        print(epaFile)
        es=epa.EPANetSimulation(epaFile)
        es.run()
        p=epa.Node.value_type['EN_PRESSURE']
        d=epa.Node.value_type['EN_DEMAND']
        f_result = open("results/" + file_name[:-4] + ".csv", 'w')
        for key, value in es.network.nodes.items():
            f_result.write(value.id + "," + str(convertUnit("pressure", value.results[p][0])) + "," + str(convertUnit("flow", value.results[d][0])) + "\n")
        print("Result exported")
        pre = {}
        for key, value in es.network.nodes.items():
            pre[value.id] = value.results[p][0]
        for key, value in ef.junctions.items():
            ef.junctions[key].pressure = pre[value.id]
        f_result.close()
    
    if save:
        ef.path = "networks/sim.inp"

# ------------------------------------
# Show graphics
# ------------------------------------
def graphPoint3D():
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    cm = plt.cm.get_cmap('RdYlBu')

    Xs = []
    Ys = []
    Zs = []

    for key, value in ef.junctions.items():
        Xs.append(float(value.posX))
        Ys.append(float(value.posY))
        Zs.append(float(value.elevation))
        if COLOR_3D_TXT is 1:
            if int(value.id) in red_3d:
                ax.text(float(value.posX), float(value.posY), float(value.elevation), str(value.id), color='red')
            elif int(value.id) in green_3d:
                ax.text(float(value.posX), float(value.posY), float(value.elevation), str(value.id), color='green')
            else:
                ax.text(float(value.posX), float(value.posY), float(value.elevation), ".", size='20')
        else:
            x.text(float(value.posX), float(value.posY), float(value.elevation), str(value.id))

    ax.set_xlim(min(Xs), max(Xs))
    ax.set_ylim(min(Ys), max(Ys))
    ax.set_zlim(min(Zs), max(Zs))
    ax.set_xlabel('Coordinated X [m]')
    ax.set_ylabel('Coordinated Y [m]')
    ax.set_zlabel('Elevation [m]')
    plt.title("Map of irrigation points")
    
    plt.show()
# ------------------------------------
# Convert unit
# ------------------------------------
def convertUnit(type, val):
    if type is "pressure":
        return val * 0.098064 # Convert [H2O m] to [bar]
    else:
        if type is "flow":
            return val * 264 * 60 # [m3/s] to gallon per minute [GPM]
        else:
            return val

# ------------------------------------
# Show graphics
# ------------------------------------
def graph2DJunctions(x, y, unit_x, unit_y, title="", regression = 0):
    fig = plt.figure()
    ax = fig.add_subplot(111)

    axe_x = []
    axe_y = []
    x_for_max_y = float(0)
    x_for_min_y = float(0)

    for key, value in ef.junctions.items():
        if int(value.id) in ef.id_cannes:
            axe_x.append(convertUnit(x, float(getattr(value, x))))
            axe_y.append(convertUnit(y, float(getattr(value, y))))
            if float(convertUnit(y, getattr(value, y))) >= max(axe_y):
                x_for_max_y = float(convertUnit(x, getattr(value, x)))
            if float(convertUnit(y, getattr(value, y))) <= min(axe_y):
                x_for_min_y = float(convertUnit(x, getattr(value, x)))

    ax.text(x_for_max_y, float(max(axe_y)), str(int(x_for_max_y)) + ": " + str(int(max(axe_y))) + " [" + unit_y + "]", fontsize=12)
    ax.text(x_for_min_y, float(min(axe_y)), str(int(x_for_min_y)) + ": " + str(int(min(axe_y))) + " [" + unit_y + "]", fontsize=12)
    sc = ax.scatter(axe_x, axe_y, c='black')
    sc = ax.scatter(x_for_max_y, max(axe_y), c='r')
    sc = ax.scatter(x_for_min_y, min(axe_y), c='r')
    if regression is 1:
        b, m = polyfit(np.asarray(axe_x), np.asarray(axe_y), 1)
        ax.plot(axe_x, b + m * np.asarray(axe_x), '-')
    if min(axe_x) >= 1:
        ax.set_xlim(min(axe_x) - (min(axe_x)/80), max(axe_x) + (max(axe_x)/80))
    else:
        ax.set_xlim(min(axe_x) - 2, max(axe_x) + (max(axe_x)/80))
    if min(axe_y) >= 1:
        ax.set_ylim(min(axe_y) - (min(axe_y)/80), max(axe_y) + (max(axe_y)/80))
    else:
        ax.set_ylim(min(axe_y) - 2, max(axe_y) + (max(axe_y)/80))

    plt.rcParams.update({'font.size': 18})
    ax.set_xlabel(x + " [" + unit_x + "]")
    ax.set_ylabel(y + " [" + unit_y + "]")
    plt.title(title)

    plt.show()

# --------------------------------------------------------------
# Show graphics for multiple nodes on the same graph
# --------------------------------------------------------------
def graph2DJunctionsMultiple(x, y, unit_x, unit_y, fig, color, title="", regression = 0):
    ax = fig.add_subplot(111)

    axe_x = []
    axe_y = []
    x_for_max_y = float(0)
    x_for_min_y = float(0)

    for key, value in ef.junctions.items():
        if int(value.id) in ef.id_cannes:
            axe_x.append(convertUnit(x, float(getattr(value, x))))
            axe_y.append(convertUnit(y, float(getattr(value, y))))
            if float(convertUnit(y, getattr(value, y))) >= max(axe_y):
                x_for_max_y = float(convertUnit(x, getattr(value, x)))
            if float(convertUnit(y, getattr(value, y))) <= min(axe_y):
                x_for_min_y = float(convertUnit(x, getattr(value, x)))
            #ax.text(float(value.elevation), float(convertUnit("pressure", value.pressure)), str(value.id), fontsize=7)

    if regression:
        ax.text(x_for_max_y, float(max(axe_y)), str(int(x_for_max_y)) + ": " + str(int(max(axe_y))) + " [" + unit_y + "]", fontsize=12)
        ax.text(x_for_min_y, float(min(axe_y)), str(int(x_for_min_y)) + ": " + str(int(min(axe_y))) + " [" + unit_y + "]", fontsize=12)
    else:
        sc = ax.scatter(axe_x, axe_y, c = color) # Transparancy: alpha=0.7
    if regression:
        b, m = polyfit(np.asarray(axe_x), np.asarray(axe_y), 1)
        ax.plot(axe_x, b + m * np.asarray(axe_x), '-')
    if min(axe_x) >= 1:
        ax.set_xlim(min(axe_x) - (min(axe_x)/80), max(axe_x) + (max(axe_x)/80))
    else:
        ax.set_xlim(min(axe_x) - 2, max(axe_x) + (max(axe_x)/80))
    if min(axe_y) >= 1:
        ax.set_ylim(min(axe_y) - (min(axe_y)/80), max(axe_y) + (max(axe_y)/80))
    else:
        ax.set_ylim(min(axe_y) - 2, max(axe_y) + (max(axe_y)/80))

    plt.rcParams.update({'font.size': 18})
    ax.set_xlabel(x + " [" + unit_x + "]")
    ax.set_ylabel(y + " [" + unit_y + "]")
    plt.title(title)

# --------------------------------------------------------
# Save netwok's general information on an HTML file
# --------------------------------------------------------
def runSummary():
    global start_time
    start_time = time.time()
    saveTitle()
    saveJunctions()
    saveReservoirs()
    saveTanks()
    savePipes()
    savePumps()
    saveValves()
    saveCoordinates()
    saveStatus()
    saveEmitters()
    saveDemands()
    readPCID()
    f = open('results/summary.html', 'w')
    p = "<h1>" + ef.title + "</h1>"
    p += "Junctions found: " + str(len(ef.junctions)) + "<br />"
    p += "Reservoirs found: " + str(len(ef.reservoirs)) + "<br />"
    p += "Tanks found: " + str(len(ef.tanks)) + "<br />"
    p += "Pipes found: " + str(len(ef.pipes)) + "<br />"
    p += "Pumps found: " + str(len(ef.pumps)) + "<br />"
    p += "Valves found: " + str(len(ef.valves)) + "<br />"
    p += "Irrigation canes found: " + str(len(ef.id_cannes)) + "<br />"
    # p += "Coordinates saved on junctions" + "<br />"
    # p += "Status saved on valves" + "<br />"
    # p += "Emitter coefficients saved on junctions" + "<br />"
    # p += "Demands saved on junctions" + "<br />"
    # p += "Points of consumption read" + "<br />"
    f.write(p)
    f.close

# --------------------------------------------------------
# Reset simulation information
# --------------------------------------------------------
def main_reset():
    if os.path.exists(ef.result_path):  # Remove the result file
        os.remove(ef.result_path)
    ef.sim_cnt = 0          # Reset the simulation counter
    ef.pipes_sim = []
    random.seed(int(time.time()))
# --------------------------------------------------------
# Reset default network
# --------------------------------------------------------
def reset():
    ef.path = PATH          # Default INP file
    Junction.id_max = 0     # Reset the max ID
    Pipe.id_max = 0
    ef.junctions.clear()    # Clean recorted junctions and pipes (TODO: delete obj)
    ef.pipes.clear()
    saveJunctions()         # Read junctions and pipes from the Epanet network file
    savePipes()
    saveCoordinates()

# ---------------------------------------------------
# Write pipe on the Epanet configuration file
# ---------------------------------------------------
def writePipe(t_leak, p_id, p_id_remove):
    
    # -- Get lines from Epanet configuration file --
    f_epanet = open(ef.path, 'r')
    lines = f_epanet.readlines()
    f_epanet.close()

    # -- Opent the temporary Epanet file for simulation --
    file_name = "sim.inp"
    partPipes = 0
    pipes_ended = 0
    f_epa = open("networks/" + file_name, 'w')
    id_line = 0
    part = 0
    p = ef.pipes[p_id]

    # -- Process every line of Epanet configuration file --
    for line in lines:
        if partPipes is 4:          # Just write the reste of the lines
            f_epa.write(line)

        if partPipes is 3:              # Search and delete the old pipe
            if detectTag(line) is not None:     # If line is out of pipes section
                partPipes = 4
            try:
                id_line = line.split()
                if len(id_line) > 1:
                    id_line = int(id_line[0])
                else:
                    id_line = 0
            except ValueError:
                pass

            if id_line is p_id_remove:            # Old pipe
                partPipes = 4
                if DEBUG:
                    print("Remove pipe") #: " + line)
                ef.pipes[p_id_remove].node2 = p.node1       # Update pipe
                ef.pipes[p_id_remove].length = p.length
                p_mod = ef.pipes[p_id_remove]
                write_p = " " + str(p_mod.id) + "               	" + str(p_mod.node1) + "               	" + str(p_mod.node2) + "               	" + str(p_mod.length) + "          	"
                write_p += str(p_mod.diameter) + "           	" + str(p_mod.roughness) + "          	" + str(p_mod.minorLoss) + "           	" + str(p_mod.status) + "  	;\n"
                f_epa.write(write_p)        # Get pipe and add them to simulation file
                if DEBUG:
                    print("Add pipe") #: " + write_p)
            else:
                f_epa.write(line)

        if partPipes is 2:
            write_p = " " + str(p.id) + "               	" + str(p.node1) + "               	" + str(p.node2) + "               	" + str(p.length) + "          	"
            write_p += str(p.diameter) + "           	" + str(p.roughness) + "          	" + str(p.minorLoss) + "           	" + str(p.status) + "  	;\n"
            f_epa.write(write_p)        # Get pipe and add them to simulation file
            if DEBUG:
                print("Add pipe")  #: " + write_p)
            partPipes = 3
            f_epa.write(line)

        if partPipes is 1:
            partPipes = 2               # Don't use header line
            f_epa.write(line)

        if partPipes is 0:
            part = getPipe(line)
            if part is None:
                f_epa.write(line)       # Write everything outside of the pipes section
            else:
                partPipes = 1
                f_epa.write(line)
    
    f_epa.close()
    ef.path = "networks/" + file_name

# ---------------------------------------------------
# Write junction on the Epanet configuration file
# ---------------------------------------------------
def writeJunction(j_id):
    f_epanet = open(ef.path, 'r')
    lines = f_epanet.readlines()
    f_epanet.close()

    file_name = "sim.inp"
    JunctionsPart = 0
    CooPart = 0
    f_epa = open("networks/" + file_name, 'w')
    for line in lines:
        s = getJunction(line)
        s_coo = getCoordinate(line)
        if JunctionsPart is 2:
            j = ef.junctions[j_id]
            write_j = " " + str(j_id) + "               	" + str(j.elevation) + "         	" + str(j.demand) + "               	          	  	;\n"
            f_epa.write(write_j)
            if DEBUG:
                print("Add junction") #: " + write_j)
            JunctionsPart = 3
        if JunctionsPart is 1:
            JunctionsPart = 2   
        if s == state_d["JUNCTIONS"]:
            JunctionsPart = 1
        f_epa.write(line)

        # -- Add junction to coordinate
        if CooPart is 2:
            line_coo = " " + str(j_id) + "               	" + str(ef.junctions[j_id].posX) + "           	" + str(ef.junctions[j_id].posY) + "\n"
            f_epa.write(line_coo)
            if DEBUG:
                print("Add coordinate") #: " + line_coo)
            CooPart = 3
        
        if s_coo is state_d["COORDINATES"]:
            CooPart = 1

        if CooPart is 1:
            CooPart = 2
    
    f_epa.close()
    ef.path = "networks/" + file_name       # Update the working file

# ------------------------------------
# Add random leaks
# ------------------------------------
def addLeaks(emitter):
    random.seed(None)
    p = random.sample(set(ef.pipes.keys()), 1)[0]      # Select a random pipe
    ef.pipes_sim.append(p)                   # Register all the simulate pipes for statistics purpose
    print("Random pipes selected for leak: " + str(ef.pipes[p]))
    j_start = ef.junctions[ef.pipes[p].node1]
    j_stop = ef.junctions[ef.pipes[p].node2]
    j_int_id = Junction.id_max + 1     # ID of the leaking junction
    Junction.id_max += 1
    j_int_el = random.randint(min(j_start.elevation, j_stop.elevation), max(j_start.elevation, j_stop.elevation))      # Random elevation between the two nodes
    j_int_x = float(min(j_start.posX, j_stop.posX)) + abs(float(j_start.posX) - float(j_stop.posX)) * 0.5              # New junction is on the actual pipe
    j_int_y = float(min(j_start.posY, j_stop.posY)) + abs(float(j_start.posY) - float(j_stop.posY)) * 0.5
    j_int = Junction(j_int_id, j_int_el, 0, "", j_int_x, j_int_y, emitter)
    ef.junctions[j_int_id] = j_int      # Add the new junction on the network
    ef.junctions[j_int_id].demand = emitter
    p1 = Pipe(Pipe.id_max + 1, j_int_id, ef.pipes[p].node2, ("{0:.2f}".format(float(ef.pipes[p].length) * 0.5)), ef.pipes[p].diameter, ef.pipes[p].roughness, ef.pipes[p].minorLoss, "Open")        # New pipe whit same physic that the old one
    ef.pipes[p].node2 = j_int.id       # Modify old pipe
    ef.pipes[p].length = ("{0:.2f}".format(float(ef.pipes[p].length) * 0.5))
    ef.pipes[p1.id] = p1
    writeJunction(j_int_id)
    writePipe(1, p1.id, p)

# ---------------------------------------------
# Add leaks on the middle of every pipe
# Return: ID of the closest junction of the leak
# ---------------------------------------------
def addLeaksMiddle(demand, coef, rand=0, persistent=0):
    pipes = {}
    # Add leaks on every pipes
    if rand is 0:
        pipes = ef.pipes.copy()
        ret = 0
    # Add leak on a random pipe
    else:
        p = random.sample(set(ef.pipes.keys()), 1)[0]
        ef.pipes_sim.append(p)      # Register all the simulate pipes for statistics purpose
        pipes[p] = ef.pipes[p]
        if DEBUG:
            print("Selected pipe: {0}".format(pipes[p]))

        if coef >= 0.5:
            ret = pipes[p].node1
        else:
            ret = pipes[p].node2

    for p, value in pipes.items():       # For every pipes
        if value.node1 in ef.junctions and value.node2 in ef.junctions: # Only if the pipe is between tow junctions (no modification for reservoir, tank, etc.)
            # Find the position of n1 in relation to n2
            position_x = 0
            position_y = 0
            j_int_el = min(ef.junctions[ef.pipes[p].node1].elevation, ef.junctions[ef.pipes[p].node2].elevation) + abs(ef.junctions[ef.pipes[p].node1].elevation - ef.junctions[ef.pipes[p].node2].elevation) * coef
            if float(ef.junctions[ef.pipes[p].node1].posX) >= float(ef.junctions[ef.pipes[p].node2].posX):
                position_x = 1
            if float(ef.junctions[ef.pipes[p].node1].posY) >= float(ef.junctions[ef.pipes[p].node2].posY):
                position_y = 1

            if DEBUG:
                print("Node {4} and {5}, p1.x = {0}, p1.y = {1}, p2.x = {2}, p2.y = {3}".format(ef.junctions[ef.pipes[p].node1].posX, float(ef.junctions[ef.pipes[p].node1].posY), float(ef.junctions[ef.pipes[p].node2].posX), float(ef.junctions[ef.pipes[p].node2].posY), ef.pipes[p].node1, ef.pipes[p].node2))
                
            if position_x is 1 and position_y is 1:
                # N1 x and y is higher
                j_int_x = (float(ef.junctions[ef.pipes[p].node2].posX) - float(ef.junctions[ef.pipes[p].node1].posX)) * coef + float(ef.junctions[ef.pipes[p].node1].posX)        # New junction is on the pipe
                j_int_y = (float(ef.junctions[ef.pipes[p].node2].posY) - float(ef.junctions[ef.pipes[p].node1].posY)) * coef + float(ef.junctions[ef.pipes[p].node1].posY)        # New junction is on the pipe
            
            if position_x is 0 and position_y is 1:
                # N1 x is lower and y is higher                
                j_int_x = (float(ef.junctions[ef.pipes[p].node2].posX) - float(ef.junctions[ef.pipes[p].node1].posX)) * coef + float(ef.junctions[ef.pipes[p].node1].posX)        # New junction is on the pipe
                j_int_y = (float(ef.junctions[ef.pipes[p].node1].posY) - float(ef.junctions[ef.pipes[p].node2].posY)) * coef + float(ef.junctions[ef.pipes[p].node2].posY)        # New junction is on the pipe
            
            if position_x is 1 and position_y is 0:
                # N1 x is higher and y is lower
                j_int_x = (float(ef.junctions[ef.pipes[p].node1].posX) - float(ef.junctions[ef.pipes[p].node2].posX)) * coef + float(ef.junctions[ef.pipes[p].node2].posX)        # New junction is on the pipe
                j_int_y = (float(ef.junctions[ef.pipes[p].node2].posY) - float(ef.junctions[ef.pipes[p].node1].posY)) * coef + float(ef.junctions[ef.pipes[p].node1].posY)        # New junction is on the pipe
            
            if position_x is 0 and position_y is 0:
                # N1 x and y is lower
                j_int_x = (float(ef.junctions[ef.pipes[p].node1].posX) - float(ef.junctions[ef.pipes[p].node2].posX)) * coef + float(ef.junctions[ef.pipes[p].node2].posX)        # New junction is on the pipe
                j_int_y = (float(ef.junctions[ef.pipes[p].node1].posY) - float(ef.junctions[ef.pipes[p].node2].posY)) * coef + float(ef.junctions[ef.pipes[p].node2].posY)        # New junction is on the pipe
            
            # New leaking junction
            Junction.id_max += 1
            j_int = Junction(Junction.id_max, j_int_el, demand, "", "{0:.2f}".format(j_int_x), "{0:.2f}".format(j_int_y), 0)
            if DEBUG:
                print("ID of the new junction: {0}".format(j_int))
            ef.junctions[Junction.id_max] = j_int      # Add the new junction on the network
            writeJunction(Junction.id_max)
            
            # New pipe from the leaking junction to the intial node 2 of the pipe
            Pipe.id_max += 1
            p1 = Pipe(Pipe.id_max, Junction.id_max, value.node2, "{0:.2f}".format(float(ef.pipes[p].length) * (1-coef)), pipes[p].diameter, pipes[p].roughness, pipes[p].minorLoss, "Open")        # New pipe whit same physic that the old one
            ef.pipes[Pipe.id_max] = p1
            
            # Modify old pipe, from initale node 1 to the new leaking node
            ef.pipes[p].node2 = j_int.id       # Modify old pipe
            ef.pipes[p].length = "{0:.2f}".format(float(ef.pipes[p].length) * coef)
            writePipe(1, p1.id, p)
            
            if DEBUG:
                print(ef.junctions[Junction.id_max])
                print(ef.pipes[p1.id])
                print(ef.pipes[value.id])
            # Retrun the closest node of the leak
            return ret
        else:
            print("No leak between " + str(value.node1) +  " - "  + str(value.node2))
            return addLeaksMiddle(demand, coef, rand, persistent)

# ----------------------------------------------------------------------
# Add a dataframe from simulation to a new line in the result CSV
# ----------------------------------------------------------------------
def sim_df_to_csv(dataframe, first=1):
    # Re-index, transpose and split the dataframe
    dataframe = dataframe.set_index('id')
    dataframe = dataframe.T
    df1_p = dataframe.add_prefix('p_')
    df1_d = dataframe.add_prefix('d_')
    df1_p = df1_p.rename(index={'pressure':str(first)})
    df1_d = df1_d.rename(index={'demand':str(first)})
    df1_p.head()
    df1_d.head()
    df1_p = df1_p.iloc[[0]]
    df1_d = df1_d.iloc[[1]]
    # Create value with the demands concatenation
    co = ""
    for index, row in df1_d.iteritems():
        co = str(co) + str(str(int(row[0])))
    df1_p['c'] = str("{0}".format(co))
    # Pressure and demand for the same simulation are on one line
    #df = pd.concat([df1_p, df1_d], axis=1, join_axes=[df1_p.index])
    df = df1_p      # Without flow columns
    if DEBUG:
        print("Size: {0} + {1} = {2}".format(len(df1_p.columns), len(df1_d.columns), len(df.columns)))
        print("CSV line length: {0}".format(len(df.columns)))
    if first is 1:
        line = df.to_csv(index = False)
    else:
        line = df.to_csv(index = False, header = False)
    # Add the created line to an existing CSV
    f = open(ef.result_path, 'a')
    f.write(line)
    f.close()

# ----------------------------------------------------------------------
# Simulation and result in CSV, return the pressure in a dataframe
# ----------------------------------------------------------------------
def sim(node = 0, first = 1):
    # Increment the simulation counter
    ef.sim_cnt += 1
    # Run external simulation script
    result_filename = "results/sim/{0}_{1}_{2}.inp".format(ntpath.basename(PATH), SIM_RATIO, LEAK)
    print("Simulation {0} in progress for leak on junction {1}...".format(ef.sim_cnt, node))
    os.system("python lib/sim.py {0} {1} {2}".format(ef.path, result_filename, node))
    if DEBUG:
        print("Done")
    # Return a dataframe of pressures
    names = ['id', 'pressure', 'demand']
    df_pre = pd.read_csv(result_filename, names=names)
    if first is 1:
        sim_df_to_csv(df_pre)
    else:
        sim_df_to_csv(df_pre, 0)
    return df_pre

# -----------------------------------------------------------------------------------
# Old simulation in intern, with the Epanettools limitation (Only for testing)
# -----------------------------------------------------------------------------------
def deprecated_intern_sim():
    es=epa.EPANetSimulation(ef.path)
    print("(DEPRECATED) Simulation in progress...")
    es.run()
    if DEBUG:
        print("Done")
    p=epa.Node.value_type['EN_PRESSURE']
    d=epa.Node.value_type['EN_DEMAND']
    
    f_result = open("results/sim_with_leak.csv", 'w')
    pre = {}
    for key, value in es.network.nodes.items():
        f_result.write(value.id + "," + str(convertUnit("pressure", value.results[p][0])) + "," + str(convertUnit("flow", value.results[d][0])) + "\n")
        if int(value.id) in ef.id_cannes:
            pre[value.id] = str(convertUnit("pressure", value.results[p][0]))
    f_result.close()

# -------------------------------------------------------------
# Return the ratio of simulaitons with negative pressure
# -------------------------------------------------------------
def pressureRatio(nbr):
    path = ef.path
    po = 0
    ng = 0
    for i in range(nbr):
        ef.path = path
        reset()
        addLeaksMiddle(convertUnit("flow", 10/60), random.randint(5, 95)/100, 1) 
        f = sim()
        neg = 0
        neg = sum(n < 0 for n in f['pressure'])
        if neg is 0:
            po = po + 1
        else:
            ng = ng + 1
        print("{0}".format(i))
    if ng is 0:
        return 0
    else:
        return(po/ng)
# ------------------------------------
# Main
# ------------------------------------
if __name__ == '__main__':
    runSummary()
    main_reset()
    #ef.sim_data()
    graphPoint3D()
    #print(drawNetwork("PC"))
    #plt.show()
    #print("Negative ratio: {0:3.2f}".format(pressureRatio(10)))
    #print("Epanet model loaded")
    #print(drawNetwork("PC"))
    #writeBD([15], 10)
    #graph2DJunctions("id", "elevation", "nbr", "m", "Elevation of every points of irrigation")
    #fig = plt.figure()
    #writeBD(0, 0)
    #graph2DJunctionsMultiple("elevation", "pressure", "m", "bar", fig, "black", "Pressure on points of irrigation when everything is closed", 1)
    #writeBD([152], 10)
    #graph2DJunctionsMultiple("elevation", "pressure", "m", "bar", fig, "red", "Pressure on points of irrigation when everything is closed", 0)
    #writeBD([22], 10)
    #graph2DJunctionsMultiple("elevation", "pressure", "m", "bar", fig, "blue", "Pressure on points of irrigation when everything is closed", 0)
    #writeBD([25], 10)
    #graph2DJunctionsMultiple("elevation", "pressure", "m", "bar", fig, "green", "Pressure on points of irrigation when everything is closed", 0)
    #writeBD([53], 10)
    #graph2DJunctionsMultiple("elevation", "pressure", "m", "bar", fig, "yellow", "Pressure on points of irrigation when everything is closed", 0)
    #writeBD([85], 10)
    #graph2DJunctionsMultiple("elevation", "pressure", "m", "bar", fig, "grey", "Pressure on points of irrigation when everything is closed", 0)
    #writeBD([53, 85], 10)
    #graph2DJunctionsMultiple("elevation", "pressure", "m", "bar", fig, "black", "Black (53 + 85) = Yellow and Grey", 0)
    #plt.show()
    #printPressure()
    #print("-- Execution time:" + str(time.time()-start_time) + " --")

    # ----------------------------------------------------------------------
    # -- Simulation for multiple leak, on every pipe between two junction --
    # ----------------------------------------------------------------------
    #addLeaksMiddle(0, 0.05)        # 5%
    #pre_05 = sim()
    #addLeaksMiddle(0, 0.5)         # 50%
    #pre_5 = sim()
    #addLeaksMiddle(0, 0.95)        # 95%
    #pre_95 = sim()

    # ----------------------------------------------------------------------
    # -- Simulation for multiple leak, on every pipe between two junction --
    # ----------------------------------------------------------------------
    #lst_sim = []
    #lst_sim_itter = []
    #cnt = 0
    #cnt_int = 0
    #print("-- Individual part-- ")
    #for i in ef.id_cannes:
    #Todo: nbr test to be modify
    #     if i < 35:
    #         cnt_int += 1
    #         writeBD([i], 1)
    #         #time.sleep(1)
    #         lst_sim.append(sim())       # Save each simulation
    #         cnt += 1
    #         if cnt > 10:
    #             print("Reimport Epanettools")
    #             cnt = 0
    #             importlib.reload(epa)
    # cnt = 0
    # print("-- Itteative part " + str(cnt_int) + " --")
    # for i in ef.id_cannes:
    #     if i < 35:
    #         writeBD([i], 1, 1)      # Keep old junctions opened
    #         lst_sim_itter.append(sim())
    #         cnt += 1
    #         if cnt > 10:
    #             print("Reimport Epanettools")
    #             cnt = 0
    #             importlib.reload(epa)
    # lst_result = []
    # lst_result_itter = []
    # for i in lst_sim_itter:
    #     res = 0
    #     for j in lst_sim:
    #         if j <= i:
    #             for k in ef.id_cannes:
    #                 res += lst_sim[i][0][k]     # Add all pressure
    #     lst_result.append(res)
    #     res = 0
    #     for k in ef.id_cannes:
    #         res += lst_sim_itter[i][0][k]
    #     lst_result_itter.append(res)
    #j_open = 1
    #while j_open is not 0:
        #j_open = input("Open (junction): ")
        #demand_open = int(convertUnit("flow", float(input("Base demand (junction): "))))
        #print("- " + str(j_open) + " - " + str(demand_open))
        #writeBD(ast.literal_eval("[" + str(j_open) + "]"), demand_open)
        #graph2DJunctions("elevation", "pressure", "m", "bar", "Pressure on points of irrigation when " + str(j_open) + " is open with " + str(demand_open) + " [cfs]", 1)
    
    # --------------------------------------------------------------
    # -- Test the performance of internal and external simulation --
    # --------------------------------------------------------------
    # tm1 = time.time()
    # for i in range(50):
    #     deprecated_intern_sim()
    # tm2 = time.time()
    # print("Simulation time for external function: {0} [ms]".format(tm2-tm1))
    # tm1 = time.time()
    # first = 1
    # for i in range(10000):
    #     reset()
    #     node = addLeaksMiddle(10, random.randint(5, 95)/100, 1) 
    #     sim(node, first)
    #     first = 0
    # tm2 = time.time()
    # print("Simulation time for external function: {0} [ms]".format(tm2-tm1))

    # print("End")
