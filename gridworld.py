import math
import numpy
import time

from gridagents import Action,GridObject,GridAgent

          
class GridPoint:

      def __init__(self,parent,x,y,max_occupants=1,occupants=None,label=None,N=None,S=None,E=None,W=None):


          self.x = x
          self.y = y
          # label can be assigned by agents 
          self._label = label
          # a point with 0 max occupants cannot be accessed (it is effectively a 'blank' grid point)
          self._maxOccupants=max_occupants
          self._occupants = []
          self._parent = parent
          # initialise neighbours in an adjacency list. The neighbours list should always have exactly 4 entries
          self._neighbours = [N,E,S,W]

      @property
      def occupants(self):
          return list(self._occupants)
    
      @property
      def occupied(self):
          return len(self._occupants) >= self._maxOccupants

      @property
      def capacity(self):
          return self._maxOccupants

      @property
      def label(self):
          return self._label

      def addNeighbour(self, neighbour, direction):
          if direction > 3 or direction < 0:
             raise IndexError("Neighbour index {0} is out of range",direction)
          if len(self._neighbours) < 3:
             raise ValueError("Grid point ({0},{1}) has an invalid or corrupted neighbour list",self.x,self.y)
          self._neighbours[direction] = neighbour

      # called by the grid world itself to place an occupant here. 
      def placeOccupant(self, parent, occupant: GridObject):
          if parent != self._parent or self.occupied:
             return False
          self._occupants.append(occupant)
          return True
       
      # called by the grid world to remove an existing occupant. Can fail if the occupant is not here.
      def removeOccupant(self, parent, occupant):
          if parent != self._parent or occupant not in self._occupants:
             return None
          else:
             return occupant
       
      # adds a label to the point. A label can be a number, colour, or any other text string
      # used to identify the point in some way
      def setLabel(self, newLabel):
          self._label = newLabel

      def clearLabel(self):
          self._label = None

      # gives an agent visibility on whether it can access the point.    
      def canGo(self, direction):
          neighbour = self._neighbours[direction]
          if neighbour is None or neighbour.occupied:
             return False
          return True
 
      # This is called by an agent attempting to occupy the space. An agent can only occupy an available space.
      def occupy(self, occupant, origin):
          # can only occupy from an adjacent GridPoint.
          if abs(origin[0]-self.x) > 1 or abs(origin[1]-self.y) > 1:
             return None
          if len(self._occupants) > self._maxOccupants:
             return None
          self._occupants.append(occupant)
          return self

      # leaves the space if the occupant can. Returns the space occupied after the attempt
      # to vacate (which can fail). Direction indicates the relative egress point. If
      # direction is None, the occupant simply 'disappears' (or is killed, deleted, or
      # whatever, the key point being that it is removed from the grid world). Returns
      # the new GridPoint occupied, which could be None, or self (if an attempt to vacate
      # failed)
      def vacate(self, occupant, direction=None):
          if occupant not in self._occupants:
             print("Occupant list for square({0},{1}): {2}".format(self.x,self.y,[occupant for occupant in self._occupants]))
             print("No such occupant: {0}:{1}".format(occupant,occupant.objectName))
             return None
          # automatically vacate
          if direction is None:
             self._occupants.remove(occupant)
             return None
          # can't leave that way
          if self._neighbours[direction] is None:
             return self
          # desired direction is already full
          if self._neighbours[direction].occupied:
             return self
          self._occupants.remove(occupant)
          occupied = self._neighbours[direction].occupy(occupant, (self.x, self.y))
          if occupied is None:
             return self
          return occupied
                
class GridWorld:

      # some convenient constants for directions
      Nowhere = -1
      North = 0
      East = 1
      South = 2
      West = 3
      
      def __init__(self,h,w,max_time=0,update_interval=1,points=None,occupants=None):
                 
          self._time = 0
          # a greater max_time than 0 will generate a world where time moves forward on each clock tick.
          self._maxTime = max_time
          # when started, the world will move in real-time increments of update_interval
          self._waitTime = update_interval
          if points is None:
             self._grid = [[GridPoint(self,x,y) for x in range(w)] for y in range(h)]
          elif occupants is None:
             self._grid = [[GridPoint(self,x,y,points[(x,y)]) for x in range(w)] for y in range(h)]
          else:
             self._grid = [[GridPoint(self,x,y,points[(x,y)],occupants[(x,y)]) for x in range(w)] for y in range(h)]
          # build up the adjacency tables. There are several efficiencies we could gain here by using constructors,
          # by not testing conditions for first and last rows/colums and instantiating them separately, and other
          # tricks, but the gains won't be huge in relative terms.
          for row in range(len(self._grid)):
              for col in range(len(self._grid[row])):
                  if row > 0 and self._grid[row-1][col].capacity > 0:
                     self._grid[row][col].addNeighbour(self._grid[row-1][col],0)
                  if col < (len(self._grid[row])-1) and self._grid[row][col+1].capacity > 0:
                     self._grid[row][col].addNeighbour(self._grid[row][col+1],1)                             
                  if row < (len(self._grid)-1) and self._grid[row+1][col].capacity > 0:
                     self._grid[row][col].addNeighbour(self._grid[row+1][col],2)
                  if col > 0 and self._grid[row][col-1].capacity > 0:
                     self._grid[row][col].addNeighbour(self._grid[row][col-1],3)
          # agents have an action at each time step. Each takes a 'turn' which is set by the order of the agent list. The
          # list contains a tuple with the agent's actual x,y position, and the agent itself. This lets us have a hidden state
          # for the agent with its position, to allow for probabilistic motions.
          self._agents = {}

      def _tick(self):
          # maxTime = 0 means run indefinitely
          if self._maxTime > 0 and self._time >= self._maxTime:
             return False
          self._time += 1
          # each agent gets a chance to do something. An action is an object containing an agent, an action code, an x,y position, 
          # an object to act upon, and a direction (so that actions can be directed at a grid point as well as from a grid point).
          for agent in self._agents.values():
              action = agent[2].chooseAction(self, agent[0], agent[1], self._grid[agent[0]][agent[1]].occupants)
              agent[2].actionResult(self._applyAction(action))
          return True
              

      def _applyAction(self, action: Action):
          # the negative action code indicates a non-action
          if action.actionCode == -1:
             return None
          # first action is always the Move action
          if action.actionCode == 0:
             destX = action.x
             destY = action.y
             print("Moving agent {0} from position ({1},{2})".format(action.agent.objectName,destX,destY))
             if action.actionDirection == 3:
                destX -= 1
             if action.actionDirection == 2:
                destY += 1
             if action.actionDirection == 1:
                destX += 1
             if action.actionDirection == 0:
                destY -= 1
             if destX < 0 or destY < 0 or destX >= len(self._grid) or destY >= len(self._grid[0]):
                return self._grid[action.y][action.x]
             newSquare = self._grid[action.y][action.x].vacate(action.agent, action.actionDirection)
             self._agents[action.agent.objectID][0] = newSquare.x
             self._agents[action.agent.objectID][1] = newSquare.y
             return newSquare
           # other actions could do other things - to follow!

      def run(self,ticks=0):
          tickCount = 0
          while (ticks == 0 or tickCount < ticks) and self._tick():
                print("Time in the world is now {0}".format(self._time))
                time.sleep(self._waitTime)
                tickCount += 1

      @property
      def runTime(self):
          return self._maxTime

      def reset(self):
          self._time = 0

      @property
      def time(self):
          return self._time

      # this will return the maximum x and y dimension of the world
      @property     
      def boundary(self):
          return (len(self._grid), len(self._grid[0]))

      # this accesses a grid location (for observations, etc.)
      def getLocation(self, x, y):
          return self._grid[y][x]

      def placeOccupant(self, occupant, row, col, isAgent=False):
          if isAgent:
             self._agents[occupant.objectID] = [col, row, occupant]
          return self._grid[row][col].placeOccupant(self, occupant) 
      
