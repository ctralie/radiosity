import OpenGL,sys,os,traceback
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from OpenGL.GL.EXT.framebuffer_object import *
from OpenGL.GL.ARB.framebuffer_object import *
from Primitives3D import *
from Graphics3D import *
from PolyMesh import *
from Cameras3D import *
from EMScene import *
from sys import argv
import random
import Image

#Purpose:
#Initialization: Duplicate radiosity materials for every face tile
#Iteration: Render scene from POV of each face tile and update radiosities
#Visualization: Render with radiosities so far

#TODO: Add function to mesh class to cut faces within a bounding box out
#(can use to make windows)
#TODO: Add tile rect function and option to invert normals on an object
#TODO: Figure out reasonable values for nearDist and farDist

#distortOnly: Only account for perspective distortion; ignore incoming angle 
#(used in conjunction with progressive radiosity since the shooting tile looks
#the other way)
class HemiCube(object):
	def __init__(self, dim = 300, distortOnly = True, nearDist = 0.01, farDist = 100.0, saveToFile = False):
		self.dim = dim
		self.nearDist = nearDist
		self.farDist = farDist
		#Initialize hemicube and scaling masks
		self.topMask = [0]*dim*dim
		#NOTE: The FOV of the face is 90 degrees
		forwardVec = Vector3D(0, 0, 1)
		total = 0.0
		for y in range(0, dim):
			for x in range(0, dim):
				index = y*dim+x
				xcoord = 2*float(x-dim/2)/float(dim)
				ycoord = 2*float(y-dim/2)/float(dim)
				dirVec = Vector3D(xcoord, ycoord, 1)
				dirVec.normalize()
				if distortOnly:
					self.topMask[index] = dirVec.Dot(forwardVec)
				else:
					self.topMask[index] = dirVec.Dot(forwardVec)**2
				total = total + self.topMask[index]

		self.sideMask = [0]*dim*(dim/2)
		leftVec = Vector3D(-1, 0, 0)
		for y in range(0, dim/2):
			for x in range(0, dim):
				index = y*dim+x
				xcoord = 2*float(x-dim/2)/float(dim)
				ycoord = 2*float(y)/float(dim)
				dirVec = Vector3D(-1, xcoord, ycoord)
				dirVec.normalize()
				if distortOnly:
					self.sideMask[index] = dirVec.Dot(leftVec)
				else:
					self.sideMask[index] = dirVec.Dot(forwardVec)*dirVec.Dot(leftVec)
				#There are 4 hemicube sides so count each weight 4x
				total = total + 4*self.sideMask[index]
		if saveToFile:
			im = Image.new("RGB", (dim, dim))
			pix = im.load()
			for y in range(0, dim):
				for x in range(0, dim):
					val = int(self.topMask[y*dim+x]*255)
					pix[x, dim-y-1] = (val, val, val)
			im.save("topMask.png")
			im = Image.new("RGB", (dim, dim/2))
			pix = im.load()
			for y in range(0, dim/2):
				for x in range(0, dim):
					val = int(self.sideMask[y*dim+x]*255)
					pix[x, dim/2-y-1] = (val, val, val)
			im.save("sideMask.png")
		#Now normalize so that the sum of all incoming energy is 1
		for i in range(0, len(self.topMask)):
			self.topMask[i] = self.topMask[i]/total
		for i in range(0, len(self.sideMask)):
			self.sideMask[i] = self.sideMask[i]/total	
				

def splitIntoRGBA(val):
	A = (0xff000000&val)>>24
	R = (0x00ff0000&val)>>16
	G = (0x0000ff00&val)>>8
	B = (0x000000ff&val)
	return [R, G, B, A]

def extractFromRGBA(R, G, B, A):
	return (((A<<24)&0xff000000) | ((R<<16)&0x00ff0000) | ((G<<8)&0x0000ff00) | (B&0x000000ff))

class Radiosity(object):
	def __init__(self):
		self.scene = EMScene()
		self.PointerDisplayList = -1
		self.needsPointerDisplayUpdate = True
		self.LightDisplayList = -1
		self.needsLightDisplayUpdate = True
		self.drawEdges = 1
		self.tiles = []
		self.hemicube = HemiCube()
	
	def loadScene(self, filename):
		self.scene.Read(filename, False)
		N = 0
		#Duplicate radiosity materials for every face tile
		for mesh in self.scene.meshes:
			RadiosityMat = mesh.EMNode.RadiosityMat
			for f in mesh.faces:
				f.RadiosityMat = RadiosityMat.clone()
			N = N + len(mesh.faces)
		#Collapse faces from every mesh into the tiles array
		i = 0
		self.tiles = [None]*N
		for mesh in self.scene.meshes:
			for f in mesh.faces:
				self.tiles[i] = f
				f.radID = i
				i = i+1
		#for tile in self.tiles:
		#	if tile.RadiosityMat:
		#		print "YEE ",
		print "Loaded radiosity scene with %i tiles"%N

	def renderPointerImage(self):
		if self.needsPointerDisplayUpdate:
			if self.PointerDisplayList != -1: #Deallocate previous display list
				glDeleteLists(self.PointerDisplayList, 1)
			self.PointerDisplayList = glGenLists(1)
			glNewList(self.PointerDisplayList, GL_COMPILE)
			glDisable(GL_LIGHTING)
			#Render all tiles with the color of their index in the tiles list
			for tile in self.tiles:
				radID = tile.radID
				#Now split the integer ID into 4 separate bytes
				[R, G, B, A] = splitIntoRGBA(radID)
				glColor4ub(R, G, B, A)
				tile.drawFilled(drawNormal=False)
			glEndList()
			self.needsPointerDisplayUpdate = False
		glCallList(self.PointerDisplayList)

	def renderLightImage(self, drawEdges = 1):
		if drawEdges == 1-self.drawEdges:
			self.drawEdges = drawEdges
			self.needsLightDisplayUpdate = True
		if self.needsLightDisplayUpdate:
			if self.LightDisplayList != -1:
				glDeleteLists(self.LightDisplayList, 1)
			self.LightDisplayList = glGenLists(1)
			glNewList(self.LightDisplayList, GL_COMPILE)
			glDisable(GL_LIGHTING)
			#Render all tiles with the color of their index in the tiles list
			for tile in self.tiles:
				rad = tile.RadiosityMat.BExcident
				glColor3f(rad.R, rad.G, rad.B)
				tile.drawFilled(drawNormal=False)
			if drawEdges == 1:
				glColor3f(0, 0, 1)
				for tile in self.tiles:
					tile.drawBorder()
			glEndList()
			self.needsLightDisplayUpdate = False
		glCallList(self.LightDisplayList)

	def shootNext(self):
		#Find tile with greatest unshot radiosity
		greatestMag = 0
		greatestTile = None
		fout = open("getRadiosities.m", "w")
		fout.write("radiosities = [")
		for i in range(0, len(self.tiles)):
			tile = self.tiles[i]
			mag = tile.RadiosityMat.BUnshot.squaredMag()
			if mag > greatestMag:
				greatestMag = mag
				greatestTile = tile
			fout.write("%g"%math.sqrt(mag))
			if i < len(self.tiles)-1:
				fout.write(", ")
		fout.write("];")
		fout.close()
		print "Greatest tile at index %i has radiosity %g"%(greatestTile.radID, math.sqrt(greatestMag))
		self.tileShootLight(greatestTile)

	def tileShootHemiFace(self, tile, dim, topFace, hemiMask, P, t, u, r):
		NTiles = len(self.tiles)
		[Rclear, Gclear, Bclear, Aclear] = splitIntoRGBA(NTiles)
		glClearColor(Rclear, Gclear, Bclear, Aclear)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		xdim = dim
		ydim = dim
		if not topFace:
			ydim = dim/2
		glViewport(0, 0, xdim, ydim)
		glScissor(0, 0, xdim, ydim)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		frustW = self.hemicube.nearDist*0.5
		if topFace:
			glFrustum(-frustW, frustW, -frustW, frustW, self.hemicube.nearDist, self.hemicube.farDist)
		else:
			glFrustum(-frustW, frustW, 0, frustW, self.hemicube.nearDist, self.hemicube.farDist)
		gotoCameraFrame(t, u, r, P)
		self.renderPointerImage()
		glutSwapBuffers()
		pixels = glReadPixelsb(0, 0, xdim, ydim, GL_RGBA, GL_UNSIGNED_BYTE)
		area = tile.getArea()
		for y in range(0, ydim):
			for x in range(0, xdim):
				pix = pixels[x][ydim-y-1]
				tileIndex = extractFromRGBA(pix[0], pix[1], pix[2], pix[3])
				if tileIndex < NTiles:
					#Here is the meat of the radiosity algorithm
					otherTile = self.tiles[tileIndex]
					dirVec = tile.getCentroid() - otherTile.getCentroid()
					dirVec.normalize()
					#weight = (area/otherTile.getArea())*hemiMask[y*ydim+x]*(dirVec.Dot(otherTile.getNormal()))
					weight = (area/otherTile.getArea())*(dirVec.Dot(otherTile.getNormal()))/float(dim*dim*3)
					toAdd = weight*tile.RadiosityMat.BUnshot
					toAdd.Scale(otherTile.RadiosityMat.p) #Scale by the reflectance of the tile
					otherTile.RadiosityMat.BUnshot = otherTile.RadiosityMat.BUnshot + toAdd
					otherTile.RadiosityMat.BExcident = otherTile.RadiosityMat.BExcident + toAdd		
		
	def tileShootLight(self, tile):
		P = tile.getCentroid()
		t = tile.getNormal()
		u = (tile.edges[0].v1.pos - tile.edges[0].v2.pos)
		u.normalize()
		r = t % u
		dim = self.hemicube.dim		
		
		#Top face of hemicube
		self.tileShootHemiFace(tile, dim, True, self.hemicube.topMask, P, t, u, r)
		#Left face of hemicube
		self.tileShootHemiFace(tile, dim, False, self.hemicube.sideMask, P, -r, t, -u)
		#Right face of hemicube
		self.tileShootHemiFace(tile, dim, False, self.hemicube.sideMask, P, r, t, u)
		#Above face of hemicube
		self.tileShootHemiFace(tile, dim, False, self.hemicube.sideMask, P, u, t, r)
		#Below face of hemicube
		self.tileShootHemiFace(tile, dim, False, self.hemicube.sideMask, P, -u, t, -r)
		
		tile.RadiosityMat.BUnshot = RGB3D(0, 0, 0)
		self.needsLightDisplayUpdate = True

	#http://www.cmsoft.com.br/index.php?option=com_content&view=category&layout=blog&id=99&Itemid=150
	def tileGatherLight(self, tile):
		dim = self.hemicube.dim
		frustW = self.hemicube.nearDist*0.5
		glClearColor(0.0, 0.0, 0.0, 0.0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		glViewport(0, 0, dim, dim)
		glScissor(0, 0, dim, dim)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		glFrustum(-frustW, frustW, -frustW, frustW, self.hemicube.nearDist, self.hemicube.farDist)
		P = tile.getCentroid()
		t = tile.getNormal()
		u = (tile.edges[0].v1.pos - tile.edges[0].v2.pos)
		u.normalize()
		r = t % u
		gotoCameraFrame(t, u, r, P)
		print "Rendering pointer image"
		self.renderPointerImage()
		print "Finished rendering pointer image"
		glutSwapBuffers()
		print "Reading Pixels"
		pixels = glReadPixelsb(0, 0, dim, dim, GL_RGB)
		print "Finished reading pixels"
		if False:
			im = Image.new("RGB", (dim, dim))
			pix = im.load()
			for y in range(0, dim):
				for x in range(0, dim):
					index = (y*dim+x)*3
					xp = dim-1-y
					yp = x
					pix[x, y] = (pixels[xp][yp][0], pixels[xp][yp][1], pixels[xp][yp][2])
			im.save("out.png")

if __name__ == '__main__':
	cube = HemiCube()
