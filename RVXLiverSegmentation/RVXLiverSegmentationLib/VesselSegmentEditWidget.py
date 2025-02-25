import qt
import slicer
import vtk

from RVXLiverSegmentationLib import SegmentWidget, createButton, GeometryExporter, NodeBranches, removeNodeFromMRMLScene


class VesselSegmentEditWidget(SegmentWidget):
  """
  Class responsible for editing the vessel automatic segmentation
  """

  def __init__(self, logic, treeWizard, widgetName):
    super(VesselSegmentEditWidget, self).__init__(widgetName + " Edit Tab", widgetName.replace(" ", "") + "Tree")
    self._widgetName = widgetName
    self._vesselBranches = NodeBranches()
    self._logic = logic
    self._centerLineVolume = None
    self._setupProceedWithVesselSplittingLayout()
    self._segmentationLogic = slicer.modules.segmentations.logic()
    self._proceedButton.setEnabled(False)
    self._treeWizard = treeWizard
    self._segmentOpacity = 0.5

  def getCenterLineVolume(self):
    return self._centerLineVolume

  def _setupProceedWithVesselSplittingLayout(self):
    self._proceedButton = createButton("Proceed to vessel splitting", self.proceedToVesselSplitting)
    layout = qt.QHBoxLayout()
    layout.addWidget(self._proceedButton)
    self.insertLayout(0, layout)

  def proceedToVesselSplitting(self):
    progressText = "Preparing Vessel Splitting.\nThis may take a minute..."
    progressDialog = slicer.util.createProgressDialog(parent=self, windowTitle="Preparing Vessel Splitting",
                                                      labelText=progressText)
    progressDialog.setRange(0, 0)
    progressDialog.setModal(True)
    progressDialog.show()
    slicer.app.processEvents()

    self._removePreviousCenterLineVolume()
    self._extractCenterLine()
    self._addSegmentationNodes(self._vesselBranches.names())
    self._proceedButton.setEnabled(False)
    self._segmentNode.GetDisplayNode().SetOpacity3D(self._segmentOpacity)
    self._prepareSplittingTools()

    progressDialog.hide()

  def _extractCenterLine(self):
    branchVolume = self._getSegmentClosedModel(self._segmentNodeName)
    if self._hasInvalidVolume(branchVolume):
      return

    startPoints, endPoints = self._vesselBranches.startPoints(), self._vesselBranches.endPoints()
    self._centerLineVolume = self._logic.centerLineFilterFromNodePositions(branchVolume, startPoints, endPoints)
    self._centerLineVolume.SetName(self._segmentNodeName + "CenterLine")

  def _prepareSplittingTools(self):
    # Get segmentation editor widget
    segmentEditorNode = self._segmentationWidget.mrmlSegmentEditorNode()

    # Prepare scissors with fill inside button
    self._selectScissorsWithFillInsideOption(segmentEditorNode)

    # Set filtered segment as vessel tree
    treeId = self._segmentNode.GetSegmentation().GetSegmentIdBySegmentName(self._segmentNodeName)
    segmentEditorNode.SetMaskSegmentID(treeId)

    # Allow editing inside a segment only
    segmentEditorNode.SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedInsideSingleSegment)

  def _selectScissorsWithFillInsideOption(self, segmentEditorNode):
    segmentEditorNode.SetActiveEffectName("Scissors")
    activeEffect = self._segmentationWidget.activeEffect()
    if activeEffect is None:
      return

    activeEffectOptionFrame = activeEffect.optionsFrame()
    fillInsideButton = None
    for child in activeEffectOptionFrame.children():
      if not hasattr(child, "text"):
        continue

      if "fill inside" in child.text.lower():
        fillInsideButton = child
        break

    if fillInsideButton is not None:
      fillInsideButton.click()

  def _getSegmentClosedModel(self, segmentName):
    modelName = "{}Model".format(segmentName)
    removeNodeFromMRMLScene(modelName)

    polyData = vtk.vtkPolyData()
    segmentId = self._segmentationObj().GetNthSegmentID(0)
    self._segmentationLogic.GetSegmentClosedSurfaceRepresentation(self._segmentNode, segmentId, polyData)

    model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode")
    model.SetAndObservePolyData(polyData)
    model.SetName(modelName)
    return model

  def _hasInvalidVolume(self, volume):
    return volume.GetPolyData().GetNumberOfPolys() == 0

  def _removePreviousCenterLineVolume(self):
    removeNodeFromMRMLScene(self._centerLineVolume)
    self._centerLineVolume = None

  def onVesselSegmentationChanged(self, vesselLabelMap, vesselBranches):
    self.clear()
    self._importLabelMap(vesselLabelMap)
    self._vesselBranches = vesselBranches
    self._proceedButton.setEnabled(True)
    self.setVisibleInScene(self.visible)

  def _importLabelMap(self, vesselLabelMap):
    self._segmentationLogic.ImportLabelmapToSegmentationNode(vesselLabelMap, self._segmentNode)
    self._segmentNode.GetDisplayNode().SetOpacity3D(1)

    # Raise if segmentation is empty
    if self._segmentationObj().GetNumberOfSegments() < 1:
      raise ValueError("Failed to extract vessel tree from vesselness volume.")

    # Rename imported segment
    self._segmentationObj().GetNthSegment(0).SetName(self._segmentNodeName)

  def getGeometryExporters(self):
    exporters = super(VesselSegmentEditWidget, self).getGeometryExporters()
    if self._centerLineVolume is not None:
      exporters.append(GeometryExporter(**{self._centerLineVolume.GetName(): self._centerLineVolume}))

    return exporters

  def setVisibleInScene(self, isVisible):
    self._treeWizard.setVisibleInScene(isVisible)
    if self._centerLineVolume is not None:
      self._centerLineVolume.SetDisplayVisibility(isVisible)

  def hideEvent(self, event):
    self.setVisibleInScene(False)
    super(VesselSegmentEditWidget, self).hideEvent(event)

  def showEvent(self, event):
    self.setVisibleInScene(True)
    super(VesselSegmentEditWidget, self).showEvent(event)

  def clear(self):
    super(VesselSegmentEditWidget, self).clear()
    self._removePreviousCenterLineVolume()

  def _segmentationObj(self):
    return self._segmentNode.GetSegmentation()


class PortalVesselEditWidget(VesselSegmentEditWidget):
  def __init__(self, logic, treeWizard):
    super(PortalVesselEditWidget, self).__init__(logic, treeWizard, "Portal Vessels")


class IVCVesselEditWidget(VesselSegmentEditWidget):
  def __init__(self, logic, treeWizard):
    super(IVCVesselEditWidget, self).__init__(logic, treeWizard, "IVC Vessels")
