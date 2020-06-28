import asyncio
import json
import logging
import websockets
import png
import threading
import time
import random
import math 
import os
logging.basicConfig()

maps = []
for picture in os.listdir("maps"):
	if(picture != "lobby.png"):
		maps.append(picture[:-4])

PLAYERS = []

guninfo = [{"name":"pistol", "automatic":False, "range":8, "damage":2, "spread":2},{"name":"uzi", "automatic":True, "range":4, "damage":1, "spread":3},{"name":"shotgun", "automatic":False, "range":6, "damage":1, "spread":4},{"name":"railgun", "automatic":False, "range":12, "damage":6, "spread":0}, {"name":"rockets", "automatic":False}, {"name":"mines", "automatic":False}, {"name":"fake walls", "automatic":False}, {"name":"barrels", "automatic":False}]

boxinfo = [{"name":"health", "maxammo":20},{"name":"pistol", "maxammo":50},{"name":"uzi", "maxammo":200},{"name":"shotgun", "maxammo":40},{"name":"railgun", "maxammo":24}, {"name":"rockets", "maxammo":15}, {"name":"mines", "maxammo":15}, {"name":"fake walls", "maxammo":20}, {"name":"barrels", "maxammo":20}]

def startingguns():
	outgoing = []
	for gun in guninfo:
		ammo = 0
		if(gun["name"] == "pistol"):
			ammo = 50
		outgoing.append({"name":gun["name"], "ammo":ammo})
	return outgoing

def loadmap(mapname):
	global zombiespawns
	global playerspawns
	global boxspawns
	global mapheight
	global mapwidth
	global unitmap
	global zombiemap
	global pathmap
	global wallmap
	global DEMONS
	global ROCKETS
	global FAKEWALLS
	global BARRELS
	global MINES
	global BOXES
	global ZOMBIES
	global zombiewave
	global zombiequeue
	global demonwave
	global demonqueue
	global currentmap
	global tosendmap
	global VOTINGSTATIONS
	global SIGNS

	currentmap = mapname
	VOTINGSTATIONS = []
	SIGNS = []
	DEMONS = []
	ROCKETS = []
	FAKEWALLS = []
	BARRELS = []
	MINES = []
	BOXES = []
	ZOMBIES = []
	zombiewave = 0
	zombiequeue = 0
	demonwave = 0
	demonqueue = 0

	reader = png.Reader("maps/"+mapname+".png")
	wallmap = reader.read()
	wallmap = wallmap[2]
	wallmap = list(wallmap)

	for line in range(len(wallmap)):
		wallmap[line] = list(wallmap[line])
		counter = 0
		pixel = []
		newline = []
		for value in range(len(wallmap[line])):
			pixel.append(wallmap[line][value])
			counter += 1
			if(counter == 3):
				if(pixel == [255,255,255]):
					newline.append(0)
				elif(pixel == [0,0,0]):
					newline.append(1)
				elif(pixel == [255,0,0]):
					newline.append(2)
				elif(pixel == [0,0,255]):
					newline.append(3)
				elif(pixel == [255,255,0]):
					newline.append(4)
				pixel = []
				counter = 0
		wallmap[line] = newline.copy()
		newline = []

	if(currentmap == "lobby"):
		votesection = []
		for x in range(len(wallmap[0])):
			votesection.append(0)

		votesection[0] = 1
		votesection[-1] = 1
		votesection[1] = 5
		votesection[-2] = 5

		for x in range(math.ceil(len(maps)/2)):
			wallmap.insert(-1, votesection.copy())
		del(votesection)

	mapheight = len(wallmap)
	mapwidth = len(wallmap[0])

	unitmap = blankmap()
	zombiemap = blankmap()
	pathmap = blankmap()
	zombiespawns = []
	playerspawns = []
	boxspawns = []

	mapsleft = maps.copy()
	for y in range(mapheight):
		for x in range(mapwidth):
			if(wallmap[y][x] == 2):
				wallmap[y][x] = 0
				zombiespawns.append([x,y])
			elif(wallmap[y][x] == 3):
				wallmap[y][x] = 0
				playerspawns.append([x,y])
			elif(wallmap[y][x] == 4):
				wallmap[y][x] = 0
				boxspawns.append([[x,y],0])
			elif(wallmap[y][x] == 5):
				wallmap[y][x] = 0
				if(len(mapsleft) > 0):
					SIGNS.append(sign(mapsleft[0], [x,y]))
					VOTINGSTATIONS.append(votingstation(mapsleft[0], [x,y]))
					del(mapsleft[0])

	tosendmap = []
	for user in PLAYERS:
		user.respawn(clear = False)
		user.mapvote = False
		tosendmap.append(user)

def blankmap():
	blankmap = []
	for y in range(mapheight):
		blankmap.append([])
		for x in range(mapwidth):
			blankmap[y].append([])
	return blankmap

def checkborder(coords):
	output = True
	if(coords[0] < 0 or coords[1] < 0 or coords[0] >= mapwidth or coords[1] >= mapheight):
		output = False
	return output

lastTime = None
maxFrameTime = 0;
def waitFramerate(T): #TODO if we have enough time, call the garbage collector
	global lastTime, maxFrameTime
	ctime = time.monotonic()
	if lastTime:
		frameTime = ctime-lastTime
		sleepTime = T-frameTime
		if frameTime > maxFrameTime:
			maxFrameTime = frameTime
			print("Frame took "+str(maxFrameTime))
		lastTime = lastTime+T
		if sleepTime > 0:
			time.sleep(sleepTime)
	else:
		lastTime = ctime

class sign:
	moveable = False
	shootable = True
	walkable = True
	def __init__(self, message, coords):
		global unitmap
		unitmap[coords[1]][coords[0]].append(self)
		self.message = message
		self.coords = coords
		self.partialcoords = [.5,.5]
		self.health = 1

class votingstation:
	moveable = False
	shootable = False
	walkable = True
	def __init__(self, mapchoice, coords):
		global unitmap
		unitmap[coords[1]][coords[0]].append(self)
		self.mapchoice = mapchoice
		self.coords = coords

class rocket:
	def __init__(self, owner):
		self.coords = [owner.coords[0]+owner.partialcoords[0], owner.coords[1]+owner.partialcoords[1]]
		self.direction = owner.facedir
		self.velocity = .9
		self.owner = owner
	def move(self):
		vector = [math.cos(self.direction)*self.velocity*.5,math.sin(self.direction)*self.velocity*.5]
		endcoords = [self.coords[0]+vector[0], self.coords[1]+vector[1]]
		hit = bulletcheck(self.coords, self.direction, self.velocity, self.owner)
		for unit in hit[0]:
			explosion(unit.coords, 3, 10)
			ROCKETS.remove(self)
		self.coords = [endcoords[0], endcoords[1]]
		self.velocity += .05

class box:
	moveable = False
	shootable = False
	walkable = True
	def __init__(self, coords, ammo = False):
		if not(ammo):
			ammo = random.choice(boxinfo)
			ammo = {"name":ammo["name"], "ammo":random.randint(1,ammo["maxammo"])}
		self.coords = coords
		self.ammo = ammo
		self.health = False
		unitmap[coords[1]][coords[0]].append(self)

class enemy:
	moveable = True
	shootable = True
	walkable = False
	def __init__(self, x, y):
		self.coords = [x, y]
		unitmap[y][x].append(self)
		zombiemap[y][x].append(self)
		self.partialcoords = [random.randint(1,9)/10, random.randint(1,9)/10]
		self.movement = 1
		self.direction = [0,0]
		self.radius = .4

	def decidedirection(self):
		self.movement = 0
		zombiemap[self.coords[1]][self.coords[0]].remove(self)
		directions = [[1,0],[-1,0],[0,1],[0,-1],[0,0]]
		directionblocked = True
		while(directionblocked):
			directionblocked = False
			if(pathmap[self.coords[1]][self.coords[0]] in directions):
				self.direction = pathmap[self.coords[1]][self.coords[0]]
			else:
				if(directions):
					self.direction = random.choice(directions)
				else:
					self.direction = [0,0]
					break
			directions.remove(self.direction)
			newcoords = [self.coords[0]+self.direction[0], self.coords[1]+self.direction[1]]
			if not(checkborder(newcoords)):
				directionblocked = True
				continue
			zombieinfront = zombiemap[newcoords[1]][newcoords[0]]
			if(zombieinfront):
				directionblocked = True
			if(wallmap[newcoords[1]][newcoords[0]]):
				directionblocked = True
			unitinfront = unitmap[newcoords[1]][newcoords[0]]
			for unit in unitinfront:
				if not(unit.walkable):
					self.attack(unit)
					self.direction = [0,0]

	def move(self):
		unitmap[self.coords[1]][self.coords[0]].remove(self)
		if(self.movement > .99):
			self.movedblock()
		self.partialcoords = [self.partialcoords[0]+(.1*self.direction[0]), self.partialcoords[1]+(.1*self.direction[1])]
		self.movement += .1
		if(self.partialcoords[0] < 0):
			self.coords[0] -= 1
			self.partialcoords[0] += 1.0
		if(self.partialcoords[0] > 1):
			self.coords[0] += 1
			self.partialcoords[0] -= 1.0
		if(self.partialcoords[1] < 0):
			self.coords[1] -= 1
			self.partialcoords[1] += 1.0
		if(self.partialcoords[1] > 1):
			self.coords[1] += 1
			self.partialcoords[1] -= 1.0
		unitmap[self.coords[1]][self.coords[0]].append(self)

class demon(enemy):
	def __init__(self, x, y):
		enemy.__init__(self, x, y)
		self.health = 20

	def movedblock(self):
		self.decidedirection()
		potentials = []
		for unit in PLAYERS:
			xdistance = abs(self.coords[0] - unit.coords[0])
			ydistance = abs(self.coords[1] - unit.coords[1])
			distance = xdistance + ydistance
			if(xdistance <= 4 and ydistance <= 4):
				potentials.append([distance, unit])
		if(potentials):
			potentials.sort(key = lambda x : x[0])
			for potential in potentials:
				unit = potential[1]
				self.facedir = math.atan2((unit.partialcoords[1]+unit.coords[1])-(self.partialcoords[1]+self.coords[1]),(unit.partialcoords[0]+unit.coords[0])-(self.partialcoords[0]+self.coords[0]))
				hit = bulletcheck([self.coords[0]+self.partialcoords[0], self.coords[1]+self.partialcoords[1]], self.facedir, potential[0], self, True, False)[0]
				allbets = True
				for thing in hit:
					if(isinstance(thing, wall)):
						allbets = False
				if(allbets):
					ROCKETS.append(rocket(self))
					self.direction = [0,0]
					break
		zombiemap[self.coords[1]+self.direction[1]][self.coords[0]+self.direction[0]].append(self)

	def attack(self, target):
		if(isinstance(target, player) or isinstance(target, fakewall) or isinstance(target, barrel)):
			target.health = 0

	def die(self):
		explosion(self.coords, 3, 10)
		if(self in zombiemap[self.coords[1]][self.coords[0]]):
			zombiemap[self.coords[1]][self.coords[0]].remove(self)
		elif(self in zombiemap[self.coords[1]+self.direction[1]][self.coords[0]+self.direction[0]]):
			zombiemap[self.coords[1]+self.direction[1]][self.coords[0]+self.direction[0]].remove(self)
		unitmap[self.coords[1]][self.coords[0]].remove(self)
		toboxornottobox = random.randint(1,1)
		if(toboxornottobox == 1):
			BOXES.append(box(self.coords))
		DEMONS.remove(self)

class zombie(enemy):
	def __init__(self, x, y):
		enemy.__init__(self, x, y)
		self.health = 10

	def movedblock(self):
		self.radius = .4
		self.decidedirection()
		zombiemap[self.coords[1]+self.direction[1]][self.coords[0]+self.direction[0]].append(self)

	def attack(self, target):
		if(isinstance(target, player)):
			target.health -= 2
			self.radius = 1.5

	def die(self):
		if(self in zombiemap[self.coords[1]][self.coords[0]]):
			zombiemap[self.coords[1]][self.coords[0]].remove(self)
		else:
			zombiemap[self.coords[1]+self.direction[1]][self.coords[0]+self.direction[0]].remove(self)
		unitmap[self.coords[1]][self.coords[0]].remove(self)
		toboxornottobox = random.randint(1,3)
		if(toboxornottobox == 1):
			BOXES.append(box(self.coords))
		ZOMBIES.remove(self)

def intersectline(lineone, linetwo):
	x1 = lineone[0][0]
	y1 = lineone[0][1]
	x2 = lineone[1][0]
	y2 = lineone[1][1]
	x3 = linetwo[0][0]
	y3 = linetwo[0][1]
	x4 = linetwo[1][0]
	y4 = linetwo[1][1]
	blah = (y4-y3)*(x2-x1) - (x4-x3)*(y2-y1)
	if(blah != 0):
		uA = ((x4-x3)*(y1-y3) - (y4-y3)*(x1-x3)) / blah
		uB = ((x2-x1)*(y1-y3) - (y2-y1)*(x1-x3)) / blah
		if(uA >= 0 and uA <= 1 and uB >= 0 and uB <= 1):
			return [x1+(uA*(x2-x1)), y1+(uA*(y2-y1))]
	return False

class player:
	moveable = True
	shootable = True
	walkable = False
	def __init__(self, websocket):
		global unitmap
		global tosendmap
		self.websocket = websocket
		self.health = 20
		self.coords = [1,1]
		unitmap[self.coords[1]][self.coords[0]].append(self)
		self.partialcoords = [.5,.5]
		self.selectedgun = 0
		self.facedir = 0.0 #facing direction in radians
		self.name = {"name":"player", "color":"#0000ff"}
		self.actions = {"up":False, "down":False, "left":False, "right":False, "prev":False, "next":False, "fire":False}
		self.gunready = True
		self.respawntimer = 300
		self.immunewall = False
		self.move = False
		self.mapvote = False
		self.radius = .4
		tosendmap.append(self)#puts self on the list of people that need the map

	def setfacedir(self):
		vec = [0,0]
		if(self.actions["up"]):
			vec[1]-=1
		if(self.actions["down"]):
			vec[1]+=1
		if(self.actions["left"]):
			vec[0]-=1
		if(self.actions["right"]):
			vec[0]+=1
		if vec[0] != 0 or vec[1] != 0:#if 0 vector, don't change facing direction
			self.facedir = math.atan2(vec[1], vec[0])
			self.move = True
		else:
			self.move = False
	def respawn(self, clear = True):
		self.gunready = True
		if(clear):
			if(self in unitmap[self.coords[1]][self.coords[0]]):
				unitmap[self.coords[1]][self.coords[0]].remove(self)
		self.health = 20
		self.coords = random.choice(playerspawns)
		self.partialcoords = [.5,.5]
		self.selectedgun = 0
		self.guns = startingguns()
		self.respawntimer = 300
		unitmap[self.coords[1]][self.coords[0]].append(self)
	def fire(self):
		if(self.guns[self.selectedgun]["name"] == "mines"):
			placing = True
			for unit in unitmap[self.coords[1]][self.coords[0]]:
				if(isinstance(unit, mine) or isinstance(unit, fakewall) or isinstance(unit, barrel)):
					placing = False
					break
			if(placing):
				MINES.append(mine(self.coords, self))
			else:
				self.guns[self.selectedgun]["ammo"] += 1
			return True
		if(self.guns[self.selectedgun]["name"] == "fake walls"):
			placing = True
			for unit in unitmap[self.coords[1]][self.coords[0]]:
				if(isinstance(unit, fakewall) or isinstance(unit, mine) or isinstance(unit, barrel)):
					placing = False
					break
			if(placing):
				FAKEWALLS.append(fakewall(self.coords))
				self.immunewall = FAKEWALLS[-1]
			else:
				self.guns[self.selectedgun]["ammo"] += 1
			return True
		if(self.guns[self.selectedgun]["name"] == "barrels"):
			placing = True
			for unit in unitmap[self.coords[1]][self.coords[0]]:
				if(isinstance(unit, fakewall) or isinstance(unit, mine) or isinstance(unit, barrel)):
					placing = False
					break
			if(placing):
				BARRELS.append(barrel(self.coords))
				self.immunewall = BARRELS[-1]
			else:
				self.guns[self.selectedgun]["ammo"] += 1
			return True
		if(self.guns[self.selectedgun]["name"] == "rockets"):
			ROCKETS.append(rocket(self))
			return True
		startcoords = [self.coords[0]+self.partialcoords[0], self.coords[1]+self.partialcoords[1]]
		spreadpossible = guninfo[self.selectedgun]["spread"]
		spread = random.randint(spreadpossible*-1, spreadpossible)/20
		bulletdir = self.facedir+spread
		if(guninfo[self.selectedgun]["name"] == "railgun"):
			hit = bulletcheck(startcoords, bulletdir, guninfo[self.selectedgun]["range"], self, True)
		else:
			hit = bulletcheck(startcoords, bulletdir, guninfo[self.selectedgun]["range"], self)
		if(hit[0]):
			for unit in hit[0]:
				unit.health -= guninfo[self.selectedgun]["damage"]

def bulletcheck(startcoords, radian, distance, immune, piercing = False, show = True):
	possible = []
	startwhole = [math.floor(startcoords[0]), math.floor(startcoords[1])]
	vector = [math.cos(radian), math.sin(radian)]
	tofor = 0
	toforo = 1
	if(abs(vector[1]) > abs(vector[0])):
		tofor = 1
		toforo = 0
	d = [vector[0]*distance, vector[1]*distance]
	endcoords = [startcoords[0]+d[0], startcoords[1]+d[1]]
	if(startcoords[tofor] < endcoords[tofor]):
		toin = range(round(startcoords[tofor]), round(endcoords[tofor]))
	else:
		toin = range(round(endcoords[tofor]), round(startcoords[tofor]))
	coords = [0,0]
	for toinchk in toin:
		coords[tofor] = toinchk
		coords[toforo] = round(startwhole[toforo] + d[toforo] * (coords[tofor] - startwhole[tofor]) / d[tofor])
		coords = [round(coords[0]), round(coords[1])]
		possible.append([coords[0],coords[1]])
	directions = [[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1]]
	trials = []
	for square in possible:
		for direction in directions:
			trial = [square[0]+direction[0], square[1]+direction[1]]
			trials.append([trial[0], trial[1]])
	for trial in trials:
		if not(trial in possible):
			possible.append([trial[0],trial[1]])
	breakout = False
	for square in reversed(range(len(possible))):
		if(possible[square][0] < 0 or possible[square][0] >= mapwidth or possible[square][1] < 0 or possible[square][1] >= mapheight):
			del(possible[square])
	possibleunits = []
	for square in possible:
		if(wallmap[square[1]][square[0]] == 1):
			possibleunits.append(wall([square[0], square[1]]))
			continue
		for unit in unitmap[square[1]][square[0]]:
			if not(unit == immune or unit.shootable == False):
				possibleunits.append(unit)
	sides = [[[.3,.3],[.3,-.3]],[[.3,-.3],[-.3,-.3]],[[-.3,-.3],[-.3,.3]],[[-.3,.3],[.3,.3]]]#right, top, left, bottom
	wallsides = [[[.5,.5],[.5,-.5]],[[.5,-.5],[-.5,-.5]],[[-.5,-.5],[-.5,.5]],[[-.5,.5],[.5,.5]]]
	tocheck = []
	if(radian > 1.56 or radian < -1.58):
		tocheck.append(0)
	if(radian > 0 and radian < 3.14):
		tocheck.append(1)
	if(radian > -1.57 and radian < 1.57):
		tocheck.append(2)
	if(radian < 0 and radian > -3.14):
		tocheck.append(3)

	possibleunits.sort(key = lambda x : math.sqrt((startcoords[0] - (x.coords[0]+x.partialcoords[0]))**2 + (startcoords[1] - (x.coords[1]+x.partialcoords[1]))**2))

	breakout = False
	output = []
	for unit in possibleunits:
		unitcoords = [unit.coords[0]+unit.partialcoords[0], unit.coords[1]+unit.partialcoords[1]]
		if(isinstance(unit, wall) or isinstance(unit, fakewall) or isinstance(unit, barrel)):
			for side in tocheck:
				intersect = intersectline([startcoords,endcoords], [[unitcoords[0]+wallsides[side][0][0],unitcoords[1]+wallsides[side][0][1]],[unitcoords[0]+wallsides[side][1][0],unitcoords[1]+wallsides[side][1][1]]])
				if(intersect):
					endcoords = intersect
					output.append(unit)
					breakout = True
					break
			if(breakout):
				break
		hit = False
		for side in tocheck:
			intersect = intersectline([startcoords,endcoords], [[unitcoords[0]+sides[side][0][0],unitcoords[1]+sides[side][0][1]],[unitcoords[0]+sides[side][1][0],unitcoords[1]+sides[side][1][1]]])
			if(intersect and piercing == False):
				endcoords = intersect
				output.append(unit)
				breakout = True
				break
			if(intersect):
				output.append(unit)
		if(breakout):
			break
	if(show):
		bullets.append({"start":startcoords, "end":endcoords})
	return [output,endcoords]

class wall:
	moveable = False
	shootable = True
	walkable = False
	def __init__(self, coords):
		self.health = 0
		self.coords = coords
		self.partialcoords = [.5,.5]

def distance(coordsone, coordstwo):
	output = math.sqrt((coordsone[0] - coordstwo[0])**2 + (coordsone[1] - coordstwo[1])**2)
	return output

class fakewall:
	moveable = False
	shootable = True
	walkable = False
	def __init__(self, coords):
		self.coords = coords
		self.partialcoords = [.5,.5]
		self.health = 5
		unitmap[coords[1]][coords[0]].append(self)
		self.radius = .6

class barrel:
	moveable = False
	shootable = True
	walkable = False
	def __init__(self, coords):
		self.coords = coords
		self.partialcoords = [.5,.5]
		self.health = 1
		unitmap[coords[1]][coords[0]].append(self)
		self.radius = .6

class mine:
	moveable = False
	shootable = False
	walkable = True
	def __init__(self, coords, layer):
		self.moveable = False
		self.shootable = False
		self.walkable = True
		self.coords = coords
		self.phase = 0
		self.layer = layer
		self.finalcountdown = 20
		unitmap[self.coords[1]][self.coords[0]].append(self)
		self.health = False
	def check(self):
		if(self.phase == 0):
			if not(self.layer in unitmap[self.coords[1]][self.coords[0]]):
				self.phase = 1
		elif(self.phase == 1):
			units = unitmap[self.coords[1]][self.coords[0]]
			for unit in units:
				if(unit != self):
					self.phase = 2
		elif(self.phase == 2):
			self.finalcountdown -= 1
			if(self.finalcountdown < 0):
				explosion(self.coords, 4, 6)
				MINES.remove(self)
				unitmap[self.coords[1]][self.coords[0]].remove(self)

def explosion(coords, radius, power):
	explosions.append({"coords":coords, "radius":radius})
	for x in range(radius*2+1):
		xdist = x-radius
		for y in range(radius*2+1):
			ydist = y-radius
			square = [coords[0]+xdist, coords[1]+ydist]
			if(square[0] > mapwidth-1 or square[1] > mapheight-1 or square[0] < 0 or square[1] < 0):
				continue
			damage = round(((radius - math.sqrt(xdist**2+ydist**2))/radius)*power)
			if(damage<0):
				damage = 0
			for unit in unitmap[square[1]][square[0]]:#list index out of range when firing up towards edge of map(rockets)
				if(unit.shootable):
					if(unit.health):
						unit.health -= damage

async def register(websocket):
	print("client got")
	PLAYERS.append(player(websocket))
	PLAYERS[-1].respawn()

async def unregister(websocket):
	print("client lost", websocket)
	for user in PLAYERS:
		if(user.websocket == websocket):
			unitmap[user.coords[1]][user.coords[0]].remove(user)
			PLAYERS.remove(user)

async def boxhead(websocket, path):
	global PLAYERS
	await register(websocket)
	try:
		async for message in websocket:
			data = json.loads(message)
			for user in PLAYERS:
				if(user.websocket == websocket):
					if(data["type"] == "controls"):
						user.actions = data["data"]
						user.setfacedir()
					elif(data["type"] == "name"):
						user.name = data["data"]
					elif(data["type"] == "gun"):
						user.selectedgun = data["data"]
					elif(data["type"] == "mapvote"):
						user.mapvote = data["data"]
					elif(data["type"] == "sign"):
						SIGNS.append(sign(data["data"], user.coords))
					else:
						print("Unknown type: "+data["type"])
	finally:
		await unregister(websocket)

def getZSpawn():
	trial = random.choice(zombiespawns)
	for unit in unitmap[trial[1]][trial[0]]:
		if(unit.walkable == False):
			trial = None
			break
	return trial

class Node:
	def __init__(self, coords, g, parent):#g is cost at this node
		self.coords = coords
		self.g = g
		self.h = heuristic(coords)
		self.f = self.g + self.h
		self.parent = parent

def heuristic(start):
	global PLAYERS
	output = 99999
	for user in PLAYERS:
		trial = math.sqrt((start[0]-user.coords[0])**2+(start[1]-user.coords[1])**2)
		if(trial < output):
			output = trial
	for unit in unitmap[start[1]][start[0]]:
		if(isinstance(unit, fakewall) or isinstance(unit, barrel)):
			output += 10
	return output

def search(start, goals):
	directions = [[0,1],[0,-1],[1,0],[-1,0]]
	openlist = [Node(start, 0, None)]
	lowest = openlist[0]
	statusMap = []
	for x in range(mapwidth*mapheight):
		statusMap.append(0)
	while(openlist):
		if(openlist != True):
			current = openlist[0]
			for node in openlist:#TODO: insert nodes into sorted order so you know openlist[0] is best.
				if(node.f < current.f):
					current = node
			for node in range(len(openlist)):
				if(openlist[node] == current):
					del(openlist[node])
					break
		if(current.coords in goals or pathmap[current.coords[1]][current.coords[0]] or current.g > 50 or openlist == True):
			if(current.g > 50 or openlist == True):
				current = lowest
			while current.parent:
				oldcoords = current.coords
				current = current.parent
				pathmap[current.coords[1]][current.coords[0]] = [oldcoords[0]-current.coords[0], oldcoords[1]-current.coords[1]]
			break
		for direction in directions:#create children
			allbets = True
			newcoords = [current.coords[0]+direction[0], current.coords[1]+direction[1]]
			if not(checkborder(newcoords)):
				continue
			for unit in unitmap[newcoords[1]][newcoords[0]]:
				if(isinstance(unit, player)):
					allbets = True
					break
				if(unit.walkable == False and not isinstance(unit, zombie) and not isinstance(unit, fakewall) and not isinstance(unit, barrel)):
					allbets = False
			if(wallmap[newcoords[1]][newcoords[0]] == 1 or statusMap[newcoords[0]+mapwidth*newcoords[1]] == 1):
				allbets = False
			if(allbets):
				openlist.append(Node(newcoords, current.g+1, current))
				if(openlist[-1].h < lowest.h):
					lowest = openlist[-1]
				statusMap[newcoords[0]+mapwidth*newcoords[1]] = 1
		if not(openlist):
			openlist = True

def makepathmap():
	global pathmap
	global ZOMBIES
	global PLAYERS
	goals = [unit.coords for unit in PLAYERS]
	pathmap = blankmap()
	for unit in ZOMBIES:
		search(unit.coords, goals)
	for unit in DEMONS:
		search(unit.coords, goals)

bullets = []
explosions = []
loadmap("lobby")
def MainLoop():
	global demonqueue
	global demonwave
	global zombiequeue
	global zombiewave
	global zombie
	global bullets
	global explosions
	pathingtimer = 9
	boxspawnrate = 100
	checktimer = 5
	while True:
		explosions = []
		bullets = []
		checktimer += 1
		if(checktimer >= 10):
			checktimer = 0
			zombiecount = 0
			demoncount = 0
			playercount = 0
			for line in unitmap:
				for square in line:
					for unit in square:
						if(isinstance(unit, zombie)):
							zombiecount += 1
						elif(isinstance(unit, demon)):
							demoncount += 1
						elif(isinstance(unit, player)):
							playercount += 1
			if(zombiecount != len(ZOMBIES)):
				print("there are "+str(zombiecount)+" zombies in the unitmap when there should be "+str(len(ZOMBIES)))
			if(demoncount != len(DEMONS)):
				print("there are "+str(demoncount)+" demons in the unitmap when there should be "+str(len(DEMONS)))
			if(playercount != len(PLAYERS)):
				print("there are "+str(playercount)+" zombies in the unitmap when there should be "+str(len(PLAYERS)))
			zombiecount = 0
			demoncount = 0
			for line in zombiemap:
				for square in line:
					for unit in square:
						if(isinstance(unit, zombie)):
							zombiecount += 1
						elif(isinstance(unit, demon)):
							demoncount += 1
			if(zombiecount != len(ZOMBIES)):
				print("there are "+str(zombiecount)+" zombies in the zombiemap when there should be "+str(len(ZOMBIES)))
			if(demoncount != len(DEMONS)):
				print("there are "+str(demoncount)+" demons in the zombiemap when there should be "+str(len(DEMONS)))
		if(zombiequeue == 0 and len(ZOMBIES) == 0 and demonqueue == 0 and len(DEMONS) == 0):
			zombiewave += 5
			zombiequeue = zombiewave
			demonwave += 1
			demonqueue = demonwave
		for unit in SIGNS:
			if(unit.health <= 0):
				unitmap[unit.coords[1]][unit.coords[0]].remove(unit)
				SIGNS.remove(unit)
		for unit in BARRELS:
			if(unit.health <= 0):
				unitmap[unit.coords[1]][unit.coords[0]].remove(unit)
				BARRELS.remove(unit)
				explosion(unit.coords, 4, 7)
		for unit in FAKEWALLS:
			if(unit.health <= 0):
				unitmap[unit.coords[1]][unit.coords[0]].remove(unit)
				FAKEWALLS.remove(unit)
		for unit in MINES:
			unit.check()
		for square in boxspawns:
			full = False
			units = unitmap[square[0][1]][square[0][0]]
			for unit in units:
				if(isinstance(unit, box)):
					full = True
			if not(full):
				square[1] += 1
				trial = random.randint(0,square[1])
				if(trial > boxspawnrate):
					BOXES.append(box(square[0]))
					square[1] = 0
		if(zombiequeue > 0):
			zspawn = getZSpawn()
			if zspawn != None:
				ZOMBIES.append(zombie(zspawn[0], zspawn[1]))
				zombiequeue -= 1
		if(demonqueue > 0):
			dspawn = getZSpawn()
			if dspawn != None:
				DEMONS.append(demon(dspawn[0], dspawn[1]))
				demonqueue -= 1
		if(PLAYERS):
			pathingtimer += 1
			if(pathingtimer == 10):
				pathingtimer = 0
				makepathmap()
			for unit in ZOMBIES:
				unit.move()
				if(unit.health <= 0):
					unit.die()
			for unit in DEMONS:
				unit.move()
				if(unit.health <= 0):
					unit.die()
		for unit in ROCKETS:
			if not(checkborder([math.floor(unit.coords[0]), math.floor(unit.coords[1])])):
				ROCKETS.remove(unit)
			unit.move()
		waitFramerate(1/20)
		alldown = False
		if(PLAYERS):
			alldown = True
		for user in PLAYERS:
			if(user.health < 0):
					user.health = 0
			if(user.health == 0):
				user.respawntimer -= 1
				if(user.respawntimer < 0):
					DEMONS.append(demon(user.coords[0], user.coords[1]))
					user.respawn()
				user.actions = {"up":False,"down":False,"left":False,"right":False,"fire":False}
				user.move = False
			else:
				alldown = False
			trialpartialcoords = [user.partialcoords[0], user.partialcoords[1]]
			trialcoords = [user.coords[0], user.coords[1]]
			if(user.move):
				vector = [math.cos(user.facedir)*.2,math.sin(user.facedir)*.2]
				trialpartialcoords = [trialpartialcoords[0]+vector[0], trialpartialcoords[1]+vector[1]]
			units = []
			for direction in [[0,0],[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1]]:
				newcoords = [user.coords[0]+direction[0], user.coords[1]+direction[1]]
				if(checkborder(newcoords)):
					for unit in unitmap[newcoords[1]][newcoords[0]]:
						if(unit != user and unit.walkable == False and unit != user.immunewall):
							units.append(unit)
			usercoords = [trialcoords[0]+trialpartialcoords[0], trialcoords[1]+trialpartialcoords[1]]
			for unit in units:
				unitcoords = [unit.coords[0]+unit.partialcoords[0], unit.coords[1]+unit.partialcoords[1]]
				distance = math.sqrt((unitcoords[0]-usercoords[0])**2+(unitcoords[1]-usercoords[1])**2)
				if(distance < (unit.radius + user.radius)):
					if(isinstance(unit, player) and unit.health <= 0):
						unit.health = 1
						unit.respawntimer = 300
					tomove = (unit.radius + user.radius) - distance
					vector = [unitcoords[0]-usercoords[0], unitcoords[1]-usercoords[1]]
					if(unit.moveable == True):
						tomove = tomove / 2
					usercoords = [usercoords[0]-(vector[0]*tomove), usercoords[1]-(vector[1]*tomove)]
					trialcoords = [math.floor(usercoords[0]), math.floor(usercoords[1])]
					trialpartialcoords = [usercoords[0] - math.floor(usercoords[0]), usercoords[1] - math.floor(usercoords[1])]
			if(user.actions["fire"]):
				if(user.gunready and user.guns[user.selectedgun]["ammo"] > 0):
					user.guns[user.selectedgun]["ammo"] -= 1
					user.fire()
					if(user.guns[user.selectedgun]["name"] == "shotgun"):
						for time in range(9):
							user.fire()
				if not(guninfo[user.selectedgun]["automatic"]):
					user.gunready = False
			else:
				user.gunready = True
			newsquare = False
			if(trialpartialcoords[0] < 0):
				trialcoords[0] -= 1
				trialpartialcoords[0] += 1.0
				newsquare = True
			if(trialpartialcoords[0] > 1):
				trialcoords[0] += 1
				trialpartialcoords[0] -= 1.0
				newsquare = True
			if(trialpartialcoords[1] < 0):
				trialcoords[1] -= 1
				trialpartialcoords[1] += 1.0
				newsquare = True
			if(trialpartialcoords[1] > 1):
				trialcoords[1] += 1
				trialpartialcoords[1] -= 1.0
				newsquare = True
			if(newsquare):
				user.immunewall = False
			if(checkborder(trialcoords)):
				if(wallmap[trialcoords[1]][trialcoords[0]] != 1):
					unitmap[user.coords[1]][user.coords[0]].remove(user)
					user.coords = [trialcoords[0], trialcoords[1]]
					user.partialcoords = [trialpartialcoords[0], trialpartialcoords[1]]
					for unit in unitmap[user.coords[1]][user.coords[0]]:
						if(isinstance(unit, box)):
							for gun in user.guns:
								if(unit.ammo["name"] == "health"):
									user.health += unit.ammo["ammo"]
									if(user.health > 20):
										user.health = 20
									break
								if(gun["name"] == unit.ammo["name"]):
									gun["ammo"] += unit.ammo["ammo"]
									for gun2 in boxinfo:
										if(gun2["name"] == gun["name"]):
											if(gun["ammo"] > gun2["maxammo"]):
												gun["ammo"] = gun2["maxammo"]
											break
									break
							BOXES.remove(unit)
							unitmap[user.coords[1]][user.coords[0]].remove(unit)
						if(isinstance(unit, votingstation)):
							user.mapvote = unit.mapchoice
					unitmap[user.coords[1]][user.coords[0]].append(user)

		if(alldown):
			loadmap("lobby")

		if(currentmap == "lobby"):
			mapvotes = []
			for option in maps:
				mapvotes.append([option, 0])
			ready = True
			if not(PLAYERS):
				ready = False
			for user in PLAYERS:
				if(user.mapvote):
					for option in mapvotes:
						if(option[0] == user.mapvote):
							option[1] += 1
				else:
					ready = False
			if(ready):
				mapvotes.sort(key = lambda x: x[1])
				score = mapvotes[-1][1]
				tie = []
				for entry in reversed(mapvotes):
					if(score == entry[1]):
						tie.append(entry[0])
					else:
						break
				selection = random.choice(tie)
				loadmap(selection)

		outgoing = {"type":"frame", "players":[], "zombies":[], "demons":[], "boxes":[], "camera":[], "partialcamera":[], "HUD":None, "bullets":bullets, "explosions":explosions, "mines":[], "fakewalls":[], "barrels":[], "signs":[], "log":[]}
		for unit in SIGNS:
			outgoing["signs"].append({"coords":unit.coords, "message":unit.message})
		for unit in BARRELS:
			outgoing["barrels"].append(unit.coords)
		for unit in DEMONS:
			outgoing["demons"].append({"coords":unit.coords, "partialcoords":unit.partialcoords})
		for unit in FAKEWALLS:
			outgoing["fakewalls"].append(unit.coords)
		for unit in MINES:
			outgoing["mines"].append(unit.coords)
		for user in PLAYERS:
			outgoing["players"].append({"coords":user.coords, "partialcoords":user.partialcoords, "gun":user.guns[user.selectedgun]["name"], "name":user.name, "facedir":user.facedir})
		for unit in ZOMBIES:
			outgoing["zombies"].append({"coords":unit.coords, "partialcoords":unit.partialcoords})
		for unit in BOXES:
			outgoing["boxes"].append(unit.coords)
		for user in PLAYERS:
			outgoing["camera"] = user.coords
			outgoing["partialcamera"] = user.partialcoords
			outgoing["HUD"] = {"health":user.health, "guns":user.guns, "gun":user.selectedgun}
			outgoingMsg = json.dumps(outgoing)
			asyncio.run(user.websocket.send(outgoingMsg)) #Really, we shouldn't call run each time. We need to make a separate message collector event loop handle thing
			if(user in tosendmap):
				tosendmap.remove(user)
				asyncio.run(user.websocket.send(json.dumps({"type":"mapdata", "map":wallmap})))
				print("map sent")

GameThread = None
GameThread = threading.Thread(group=None, target=MainLoop, name="GameThread")
GameThread.start()
asyncio.get_event_loop().run_until_complete(websockets.serve(boxhead, port=9001))
asyncio.get_event_loop().run_forever()
