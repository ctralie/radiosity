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

class Radiosity(object):
	def __init__(self, width = 600, height = 600):
		self.scene = EMScene()
		self.DisplayList = -1
		self.needsDisplayUpdate = True
		self.tiles = []
	
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
