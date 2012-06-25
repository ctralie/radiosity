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
#TODO: Figure out how to check depth buffer to see if it's just empty space

class HemiCube(object):
	def __init__(self, dim = 600, nearDist = 0.01, farDist = 100.0, saveToFile = False):
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
				

class Radiosity(object):
	def __init__(self):
		self.scene = EMScene()
		self.DisplayList = -1
		#The display list holding all tiles will update if this is the case
		self.needsDisplayUpdate = True
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
		print "Loaded radiosity scene with %i tiles"%N

	def renderPointerImage(self):
		if self.needsDisplayUpdate:
			if self.DisplayList != -1: #Deallocate previous display list
				glDeleteLists(self.DisplayList, 1)
			self.DisplayList = glGenLists(1)
			glNewList(self.DisplayList, GL_COMPILE)
			glDisable(GL_LIGHTING)
			#Render all tiles with the color of their index in the tiles list
			for i in range(0, len(self.tiles)):
				tile = self.tiles[i]
				radID = tile.radID
				#Now split the integer ID into 4 separate bytes
				A = (0xff000000&radID)>>24
				R = (0x00ff0000&radID)>>16
				G = (0x0000ff00&radID)>>8
				B = (0x000000ff&radID)
				glColor4ub(R, G, B, A)
				tile.drawFilled(drawNormal=False)
			glEndList()
			self.needsDisplayUpdate = False
		glCallList(self.DisplayList)

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
		t = -tile.getNormal()
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
