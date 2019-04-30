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
# Program name      : errorcomputation.py
# School            : HEIA-FR
# Author            : Lucien Aymon
# Date created      : 30.04.2019
# Purpose           : Compute the Euclidian distance between two nodes
# Revision History  :
# Date        Author      Ref    Revision
# 
# Input: ID of the first and second junction 
# Output: Euclidian distance between the two points
# ********************************************************************************;

# ------------------------------------
# Import
# ------------------------------------
import math
import sys

# Read an INP file and return coordinates
# @Return: list of ID and coordinates X and Y
def get_index(junction):
    path = 'input.inp'
    inp_file = open(path,'r')
    lines = inp_file.readlines()
    lines_coor = []
    before = True
    after = False
    add = True
    for line in lines:
        if before:
            add = False
        else:
            if "[" in line and "]" in line or line == "\n":
                after = True
        if line == "[COORDINATES]\n":
            before = False
            add = True
        if after:
            add = False
        if add:
            lines_coor.append(line)
    # Remove [Coordinates]
    lines_coor.pop(0)
    # Remove table header
    lines_coor.pop(0)
    exp = lambda x: x.strip().split('\t')
    space = lambda x: [float(y.strip()) for y in x]
    lines_coor = list(map(exp, lines_coor))
    lines_coor = list(map(space, lines_coor))
    for el in lines_coor:
        if int(el[0]) == junction:
            return el

# Compute the distance between two element
# @Return X and Y distances
def get_delta(j1, j2):
    coor = {'x': 0, 'y': 0}
    j1_index = get_index(j1)
    j2_index = get_index(j2)
    coor['x'] = abs(j1_index[1] - j2_index[1])
    coor['y'] = abs(j1_index[2] - j2_index[2])
    return coor

# Compute the euclidian distance between two element
# @Return the distance
def get_distance(j1, j2):
    dist = get_delta(j1, j2)
    dist_eucl = math.sqrt(dist['x'] ** 2 + dist['y'] ** 2)
    return "{:.4f}".format(dist_eucl)

def main():
  try:
      return get_distance(int(sys.argv[1]), int(sys.argv[2]))
  except:
      return -1
  
if __name__== "__main__":
  main()