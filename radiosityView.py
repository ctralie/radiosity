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
from Radiosity import *
from sys import argv
from time import time
import random
import Image

class Viewer(object):
	def __init__(self, filename):
		#GLUT State variables
		self.GLUTwindow_height = 800
		self.GLUTwindow_width = 800
		self.GLUTmouse = [0, 0]
		self.GLUTButton = [0, 0, 0, 0, 0]
		self.GLUTModifiers = 0
		self.keys = {}
		self.drawEdges = 0
		self.drawVerts = 0
		self.drawNormals = 0
		
		#Camera state variables
		self.radiosity = Radiosity()
		self.radiosity.loadScene(filename)
		
		self.camera = MouseSphericalCamera(self.GLUTwindow_width, self.GLUTwindow_height)
		random.seed()
		self.initGL()

	def GLUTResize(self, w, h):
		glViewport(0, 0, w, h)
		self.GLUTwindow_width = w
		self.GLUTwindow_height = h
		self.camera.pixWidth = w
		self.camera.pixHeight = h
		glutPostRedisplay()

	def GLUTRedraw(self):
		glClearColor(0.0, 0.0, 0.0, 0.0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		glViewport(0, 0, self.GLUTwindow_width, self.GLUTwindow_height)
		glScissor(0, 0, self.GLUTwindow_width, self.GLUTwindow_height)

		#Set up projection matrix
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		gluPerspective(180.0*self.camera.yfov/math.pi, float(self.GLUTwindow_width)/self.GLUTwindow_height, 0.01, 100.0)
		
		#Set up modelview matrix
		self.camera.gotoCameraFrame()	
		
		glLightfv(GL_LIGHT0, GL_POSITION, [3.0, 4.0, 5.0, 0.0]);
		glLightfv(GL_LIGHT1, GL_POSITION,  [-3.0, -2.0, -3.0, 0.0]);
		
		glEnable(GL_LIGHTING)

		#self.radiosity.renderPointerImage()
		#self.radiosity.scene.renderGL()
		self.radiosity.renderLightImage(self.drawEdges)
		glutSwapBuffers()
	
	def handleMouseStuff(self, x, y):
		y = self.GLUTwindow_height - y
		self.GLUTmouse[0] = x
		self.GLUTmouse[1] = y
		self.GLUTmodifiers = glutGetModifiers()
	
	def GLUTKeyboard(self, key, x, y):
		self.handleMouseStuff(x, y)
		self.keys[key] = True
		glutPostRedisplay()
	
	def GLUTKeyboardUp(self, key, x, y):
		self.handleMouseStuff(x, y)
		self.keys[key] = False
		if key in ['e', 'E']:
			self.drawEdges = 1 - self.drawEdges
		elif key in ['v', 'V']:
			self.drawVerts = 1 - self.drawVerts
		elif key in ['n', 'N']:
			self.drawNormals = 1 - self.drawNormals
		elif key in ['s', 'S']:
			print "Reading pixels"
			width = self.GLUTwindow_width
			height = self.GLUTwindow_height
			pixels = glReadPixelsb(0, 0, width, height, GL_RGB)
			print "Finished reading pixels"
			im = Image.new("RGB", (width, height))
			pix = im.load()
			for y in range(0, height):
				for x in range(0, width):
					index = (y*width+x)*3
					xp = height-1-y
					yp = x
					pix[x, y] = (pixels[xp][yp][0], pixels[xp][yp][1], pixels[xp][yp][2])
			im.save("out.png")
		elif key in ['g', 'G']:
			start = time()
			for i in range(0, 100):
				self.radiosity.tileGatherLight(self.radiosity.tiles[i])
			elapsed = time() - start
			print "%s seconds elapsed"%elapsed
		elif key in ['t', 'T']:
			start = time()
			for i in range(0, 1):
				self.radiosity.shootNext()
			elapsed = time() - start
			print "%s seconds elapsed"%elapsed
		glutPostRedisplay()
	
	def GLUTSpecial(self, key, x, y):
		self.handleMouseStuff(x, y)
		self.keys[key] = True
		glutPostRedisplay()
	
	def GLUTSpecialUp(self, key, x, y):
		self.handleMouseStuff(x, y)
		self.keys[key] = False
		glutPostRedisplay()
		
	def GLUTMouse(self, button, state, x, y):
		buttonMap = {GLUT_LEFT_BUTTON:0, GLUT_MIDDLE_BUTTON:1, GLUT_RIGHT_BUTTON:2, 3:3, 4:4, 5:5}
		if state == GLUT_DOWN:
			self.GLUTButton[buttonMap[button]] = 1
		else:
			self.GLUTButton[buttonMap[button]] = 0
		self.handleMouseStuff(x, y)
		glutPostRedisplay()

	def GLUTMotion(self, x, y):
		lastX = self.GLUTmouse[0]
		lastY = self.GLUTmouse[1]
		self.handleMouseStuff(x, y)
		dX = self.GLUTmouse[0] - lastX
		dY = self.GLUTmouse[1] - lastY
		if self.GLUTButton[2] == 1:
			self.camera.zoom(-dY)
		elif self.GLUTButton[1] == 1:
			self.camera.translate(dX, dY)
		else:
			self.camera.orbitLeftRight(dX)
			self.camera.orbitUpDown(dY)
		glutPostRedisplay()
	
	def initGL(self):
		glutInit('')
		glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
		glutInitWindowSize(self.GLUTwindow_width, self.GLUTwindow_height)
		glutInitWindowPosition(50, 50)
		glutCreateWindow('Viewer')
		glutReshapeFunc(self.GLUTResize)
		glutDisplayFunc(self.GLUTRedraw)
		glutKeyboardFunc(self.GLUTKeyboard)
		glutKeyboardUpFunc(self.GLUTKeyboardUp)
		glutSpecialFunc(self.GLUTSpecial)
		glutSpecialUpFunc(self.GLUTSpecialUp)
		glutMouseFunc(self.GLUTMouse)
		glutMotionFunc(self.GLUTMotion)
		
		glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
		glLightModeli(GL_LIGHT_MODEL_LOCAL_VIEWER, GL_TRUE)
		glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
		glEnable(GL_LIGHT0)
		glLightfv(GL_LIGHT1, GL_DIFFUSE, [0.5, 0.5, 0.5, 1.0])
		glEnable(GL_LIGHT1)
		glEnable(GL_NORMALIZE)
		glEnable(GL_LIGHTING)
		
		glEnable(GL_DEPTH_TEST)
		
		glutMainLoop()

if __name__ == '__main__':
	if len(argv) < 2:
		print "Usage: radiosityView <scene filepath>"
	else:
		viewer = Viewer(argv[1])
