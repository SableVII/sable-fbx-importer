
bl_info = {
    "name": "Sable's .fbx Importer",
    "author": "Sable7",
    "version": (0, 0, 1),
    "blender": (4, 0, 0),
    "location": "3D Viewport > Sidebar > Sable",
    "description": "Sable's .fbx Importer",
    "category": "Development",
}

# give Python access to Blender's functionality
import bpy
import bmesh
import re
import os

from bpy.props import *
from bpy_extras.io_utils import ImportHelper

'''class OT_sable_clean_up_imported_mesh(bpy.types.Operator):
    bl_idname = "sable.clean_up_imported_mesh"
    bl_label = "Removes things from a mesh that has been freshly imported"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        deleteVertexGroups = []
        splitString = "[Delete], [HoodieJacket]"#scn.smc_sable_vertex_groups_to_delete.split(",")
        for s in splitString:
            deleteVertexGroups.append(s.strip())            

        for object in context.selected_objects:
            if object.type == bpy.types.Object:
                print("Found imported object: " + object.name)

        for item in context.scene.smc_ob_data:
            if item.type == globs.CL_OBJECT:
                bpy.ops.object.mode_set(mode='EDIT')
                vertexGroupIndexes = []

                # Get vertex group indicies
                for deleteVertexGroupName in deleteVertexGroups:
                    try:
                        vertexGroupIndexes.append(item.ob.vertex_groups[deleteVertexGroupName].index)
                        print("VertexGroupIndex of " + deleteVertexGroupName + " is " + str(vertexGroupIndexes[len(vertexGroupIndexes) - 1]))
                    except:
                        print("Attempted to delete vertex group: " + deleteVertexGroupName + " but " + deleteVertexGroupName + " does not exist on the object")                    

                if len(vertexGroupIndexes) == 0:
                    continue

                bm = bmesh.from_edit_mesh(item.ob.data)    
                deform = bm.verts.layers.deform.active

                vertsToDelete = []
                for vertex in bm.verts:
                    vertexDeform = vertex[deform]
                    for vertexGroupIndex in vertexGroupIndexes:
                        if vertexDeform.get(vertexGroupIndex, -1) >= 0:
                            vertsToDelete.append(vertex)
                            break

                bmesh.ops.delete(bm, geom=vertsToDelete, context="VERTS")
                bmesh.update_edit_mesh(item.ob.data)

        return {'FINISHED'}'''

sable_debug = False

def sable_print(text: str) -> None:
    if sable_debug == True:
        print(text)

class SableFileInfo:
    fileName = ""
    fileNumber = ""
    filePath = ""

    def __init__(self, fileName: str, fileNumber: str, filePath: str):
        self.fileName = fileName
        self.fileNumber = fileNumber
        self.filePath = filePath


def sable_clean_up_mesh(obj: bpy.types.Object, deleteVertexGroups: list, scene: bpy.types.Scene):
    sable_print("Cleaing up Mesh: " + obj.name + " type: " + obj.type)

    if obj.type == "MESH":
        bpy.ops.object.mode_set(mode='OBJECT')        
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj 
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        vertexGroupIndexes = []

        # Get vertex group indicies
        for deleteVertexGroupName in deleteVertexGroups:
            try:
                vertexGroupIndexes.append(obj.vertex_groups[deleteVertexGroupName].index)
                sable_print("VertexGroupIndex of " + deleteVertexGroupName + " is " + str(vertexGroupIndexes[len(vertexGroupIndexes) - 1]))
            except:
                sable_print("Attempted to delete vertex group: " + deleteVertexGroupName + " but " + deleteVertexGroupName + " does not exist on the object")                    

        if len(vertexGroupIndexes) == 0:
            return

        bm = bmesh.from_edit_mesh(obj.data)    
        deform = bm.verts.layers.deform.active

        vertsToDelete = []
        for vertex in bm.verts:
            vertexDeform = vertex[deform]
            for vertexGroupIndex in vertexGroupIndexes:
                if vertexDeform.get(vertexGroupIndex, -1) >= 0:
                    vertsToDelete.append(vertex)
                    break

        bmesh.ops.delete(bm, geom=vertsToDelete, context="VERTS")
        bmesh.update_edit_mesh(obj.data)

        # if mesh is now completely empty, delete object?

        if sable_debug:
            s = obj.name + " Deleted Vetex Groups: "
            first = True
            for deleteVertexGroupName in deleteVertexGroups:
                if not first:
                    s += ", "
                first = False
                s += deleteVertexGroupName
            sable_print(s)

def sable_remove_bones_R(armatureRef, bone : bpy.types.EditBone):
    for child in bone.children:
        sable_remove_bones_R(armatureRef, child)

    if sable_debug:
        sable_print("Removed Bone: " + bone.name)

    armatureRef.edit_bones.remove(bone)

def sable_clean_up_armature(obj: bpy.types.Object, deleteBones: list, scene: bpy.types.Scene):
    sable_print("Cleaing up Armature: " + obj.name + " type: " + obj.type)

    if obj.type == "ARMATURE":
        bpy.ops.object.mode_set(mode='OBJECT')        
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj 
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')

        armature = obj.data        

        for bone in armature.edit_bones:
            boneName = bone.name
            
            ### Remove bones with 
            if bone.name.startswith("[") and boneName.endswith("]"):

                #armature.edit_bones.remove(bone)
                sable_remove_bones_R(armature, bone)
                continue

            ### Remove specified bones to delete
            if bone.name in deleteBones:
                sable_remove_bones_R(armature, bone)
                continue                

        obj.update_from_editmode()

def sable_improve_imports(context, fileInfos : SableFileInfo):
        scn = context.scene

        if (context.active_object != None):
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')

        existingObjectsSet = set()
        existingMaterialsDictionary = {}

        ### Clean up any orphaned items
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        ### Check to see if there is an armature to merge into and create existingObjectSet
        baseMergeArmature = None
        for obj in scn.objects:
            existingObjectsSet.add(obj)
            if obj.type == "ARMATURE":
                if baseMergeArmature == None:
                    baseMergeArmature = obj

        ### Clean up any objects that are inside the file but not in the scene
        for obj in bpy.data.objects:
            if obj in existingObjectsSet:
                continue
            else:
                bpy.data.objects.remove(obj)                    
                
        ### Get list of pre-exiting materials with name
        for mat in bpy.data.materials:
            # Split out the . from the material name (happens when blender loads in a material of same name)
            splitName = mat.name.split('.')
            existingMaterialsDictionary[splitName[0]] = mat

        ### Parse out imports to offset
        importsToOffset = set()
        splitImportsToOffset = scn.sable_imports_to_offset.split(",")
        for importName in splitImportsToOffset:
            importName = importName.strip()

            if importName == "":
                continue

            importsToOffset.add(importName)

        ### Get a list of all pre-existing armatures
        existingArmatures = set()
        armaturesToMergeIn = []
        for obj in scn.objects:
            if obj.type == "ARMATURE":
                existingArmatures.add(obj)

        for fileInfo in fileInfos:
            #print("File Path: " + filepath.name)
            bpy.ops.object.select_all(action='DESELECT')                    

            bpy.ops.import_scene.fbx(filepath=fileInfo.filePath, ignore_leaf_bones=True)

            # Grab newly added armatures. Base armature is needed to be found here if not found already
            for obj in scn.objects:
                if obj.type == "ARMATURE":                    
                    if (obj not in existingArmatures):
                        if baseMergeArmature == None and fileInfo.fileName == "Base":
                            baseMergeArmature = obj
                        else:
                            armaturesToMergeIn.append(obj)

                        existingArmatures.add(obj)

            if (fileInfo.fileName not in importsToOffset) == scn.sable_invert_imports_to_offset:
                bpy.ops.transform.translate(value=(0.0, 0.0, scn.sable_import_offset))



        ### Clean up Meshes
        # Parse Vertex Groups to Delete 
        deleteVertexGroups = []
        splitString = scn.sable_delete_vertex_groups.split(",")
        for s in splitString:
            s = s.strip()

            if s == "":
                continue

            deleteVertexGroups.append(s)

        for obj in scn.objects:
            if (obj not in existingObjectsSet):
                if obj.type == "MESH":                
                    #obj.select_set(True)
                    sable_clean_up_mesh(obj, deleteVertexGroups, scn)



        ### Clean up Armatures
        # Parse Bones to Delete list
        deleteBones = []
        splitString = scn.sable_delete_bones.split(",")
        for s in splitString:
            s = s.strip()

            if s == "":
                continue

            deleteBones.append(s)

        for obj in scn.objects:
            if (obj not in existingObjectsSet):
                if obj.type == "ARMATURE":
                    #obj.select_set(True)
                    sable_clean_up_armature(obj, deleteBones, scn)

        if baseMergeArmature != None:
            try:
                prevMergeSameBones = context.scene.merge_same_bones
                prevApplyTransforms = context.scene.apply_transforms
                prevJoinMeshes = context.scene.merge_armatures_join_meshes
                prevZeroWeight = context.scene.merge_armatures_remove_zero_weight_bones
                prevCleanupShapekeys = context.scene.merge_armatures_cleanup_shape_keys

                context.scene.merge_same_bones = True
                context.scene.apply_transforms = False
                context.scene.merge_armatures_join_meshes = False
                context.scene.merge_armatures_remove_zero_weight_bones = False
                context.scene.merge_armatures_cleanup_shape_keys = False

                bpy.context.scene.merge_armature_into = baseMergeArmature.name
                for arm in armaturesToMergeIn:
                    bpy.context.scene.merge_armature = arm.name                    
                    bpy.ops.cats_custom.merge_armatures()

                context.scene.merge_same_bones = prevMergeSameBones
                context.scene.apply_transforms = prevApplyTransforms
                context.scene.merge_armatures_join_meshes = prevJoinMeshes
                context.scene.merge_armatures_remove_zero_weight_bones = prevZeroWeight
                context.scene.merge_armatures_cleanup_shape_keys = prevCleanupShapekeys    

            except AttributeError:
                print("Error- Cannot merge armatures as bpy.ops.cats_custom.merge_armatures() is unable to be found")

        ### Clean Up Materials on imported objects
        bpy.ops.object.mode_set(mode='OBJECT')   
        bpy.ops.object.select_all(action='DESELECT')
        
        for obj in scn.objects:
            if (obj not in existingObjectsSet):
                if obj.type == "MESH":                
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj    
        bpy.ops.object.material_slot_remove_unused()

        ### Swap Materials
        '''for obj in scn.objects:
            if (obj not in existingObjectsSet):
                if obj.type == "MESH":                
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj'''

        ### Delete any unused materials
        materialNameToMaterialDictionary = {} #<string (material name), Material>
        for obj in scn.objects:
            if (obj not in existingObjectsSet):
                if obj.type == "MESH":
                    for materialSlot in obj.material_slots:
                        #print("Obj " + obj.name + " Material Slot[" + str(materialSlot.slot_index) + "] " + materialSlot.name)
                        matName = materialSlot.name.split('.')[0]

                        # Attempt to find simularliy named pre-existing material and swap out material for that
                        if matName.endswith("[S]"):
                            if matName in existingMaterialsDictionary:
                                materialSlot.material = existingMaterialsDictionary[matName]
                                continue

                    # Check to see if this material of the same name already esists on the model, if so, then set the slot to that material
                    if matName not in materialNameToMaterialDictionary:
                        materialNameToMaterialDictionary[matName] = materialSlot.material
                        continue
                
                    materialSlot.material = materialNameToMaterialDictionary[matName]


        ### Remove all unlinked materials
        usedMatsSet = set()
        for obj in scn.objects:
            if obj.type == "MESH":
                for mat in obj.material_slots:
                    #print("Found Mat to keep: " + mat.material.name)
                    usedMatsSet.add(mat.material)

        for mat in bpy.data.materials:                     
            if mat in usedMatsSet: # I don't know why if mat in usedMatsSet == False: always returns True x.x
                sable_print("Mat is in Set: " + mat.name)   
            else:
                sable_print("Removing Mat: " + mat.name)
                bpy.data.materials.remove(mat)
                            
        ### Join meshes
        if baseMergeArmature != None:
            try:
                bpy.ops.cats_manual.join_meshes()
            except AttributeError:
                print("Error- Cannot join meshes as bpy.ops.cats_manual.join_meshes() is unable to be found")

        ### Clean up any objects that are inside the file but not in the scene
        for obj in bpy.data.objects:
            if obj.name in scn.objects:
                continue
            else:
                bpy.data.objects.remove(obj)

        ### Clean up any remaining items
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        ### Adjust Tail of Toe bones'z Z value to equal 0
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
           
        for obj in scn.objects:
            if obj.type == "ARMATURE":
                bpy.context.view_layer.objects.active = obj
                
                bpy.ops.object.mode_set(mode='EDIT')
                if "Right toe" in obj.data.edit_bones:
                    obj.data.edit_bones["Right toe"].tail.z = 0
                if "Left toe" in obj.data.edit_bones:
                    obj.data.edit_bones["Left toe"].tail.z = 0
                bpy.ops.object.mode_set(mode='OBJECT')
            
                ### Also set In Front and Display as Wire in ViewPort Display
                obj.display_type = 'WIRE'
                obj.show_in_front = True

        

        ### Select all imported Objects
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

        for obj in scn.objects:
            if (obj not in existingObjectsSet):
                obj.select_set(True)
                if obj.type == "MESH":
                    obj.name = "Body"


        #bpy.ops.sable.clean_up_imported_mesh(context)

class OT_sable_import_fbx(bpy.types.Operator, ImportHelper):
    bl_idname = "sable.import_fbx"
    bl_label = "Imports an .fbx"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: bpy.props.StringProperty( default='*.fbx', options={'HIDDEN'} )

    files: bpy.props.CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)

    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        global sable_debug
        sable_debug = context.scene.sable_debug

        fileInfos = []
        for file in self.files:
            fileName = file.name.rstrip(".fbx")

            #print(file.name + "     " + self.directory)
            match = re.match(r"([a-zA-Z\-\_]+)(\d+(?:\.\d+)*)", fileName)
            
            if match:    # shouldn't ever fail?     
                fileInfos.append(SableFileInfo(match.group(1), match.group(2), self.directory + file.name))
                sable_print(match.group(1) + "  " + match.group(2) + "  " + self.directory + file.name)

        sable_improve_imports(context, fileInfos)

        '''try:
            bpy.context.scene.merge_armature_into = 
            print("--- Should be set")
        except:
            print("--- Failed to set thingy")

        try:
            bpy.ops.cats_custom.merge_armatures()
            print("---- Shouldve been called")
        except AttributeError:
            print("---- FAILED to call")'''

        return {'FINISHED'}
    
class OT_sable_import_all(bpy.types.Operator):
    bl_idname = "sable.import_all"
    bl_label = "Imports a bunch of .fbxs at once!"
    bl_options = {"REGISTER", "UNDO"}

    fileNameToListDict = {}
    fileNameToLatestFileDict = {}

    def execute(self, context):
        global sable_debug
        sable_debug = context.scene.sable_debug

        sable_print(context.blend_data.filepath)
        sable_print(os.path.dirname(context.blend_data.filepath))

        # Get route directory
        rootFilePath = ""
        currentFilePath = os.path.dirname(context.blend_data.filepath)
        splitPath = currentFilePath.rsplit('\\', 1)
        while len(splitPath) >= 2:
            parentFilePath = splitPath[0]
            currentFile = splitPath[1]

            currentFilePath = parentFilePath + "\\" + currentFile
            sable_print("Current Path: " + currentFilePath)
            

            if currentFile == "SableAvatar":
                rootFilePath = parentFilePath + "\\" + currentFile
                sable_print("Found Root! " + rootFilePath)
                break
        
            splitPath = parentFilePath.rsplit('\\', 1)

        if rootFilePath == "":
            sable_print("Failed to find file root :(")
            return {'FINISHED'}


        # Map out directory
        self.fileNameToListDict = {}
        self.fileNameToLatestFileDict = {}

        self.WalkDirectory_R(rootFilePath)

        # Debug
        if sable_debug:
            for key in self.fileNameToLatestFileDict.keys():
                fileInfo = self.fileNameToLatestFileDict[key]
                fileInfos = self.fileNameToListDict[key]
                s = "\n" + fileInfo.fileName + ": ["
                first = True
                for fileInfo2 in fileInfos:
                    if not first:
                        s += ", "
                    
                    first = False

                    s += "\"" + fileInfo2.fileName + fileInfo2.fileNumber + "\""
                s += "]\n"

                s += "Latest File: " + fileInfo.fileName + fileInfo.fileNumber

                sable_print(s)

        # Get a list of all the files to import
        fileInfos = []
        splitFilesToImportInput = context.scene.sable_fbx_to_import.split(",")
        for fileName in splitFilesToImportInput:
            fileName = fileName.strip()

            if fileName == "":
                continue

            if fileName in self.fileNameToLatestFileDict:
                fileInfo = self.fileNameToLatestFileDict[fileName]
                sable_print(fileInfo.filePath)                
                fileInfos.append(fileInfo)

        sable_improve_imports(context, fileInfos)


        # Get Highest Number Testing
        # Regex rejects any error causing numbers
        '''fileNames = ["Rabbits3.41.4", "Rabbits3.42", "Rabbits3.42.1", "Rabbits3.40", "Rabbits3", "Rabbits", "Rabbits4.41.4f"]
        # ([a-zA-Z]+)(\d+(?:\.\d+)*)

        numbers = []
        for fileName in fileNames:
            match = re.match(r"([a-zA-Z]+)(\d+(?:\.\d+)*)", fileName)
            
            if match:
                #print("Match: " + str(match))
                numbers.append(match.group(2))

        #numbers = ["3.4.4", "4.0", "4.45.000.0.1.0" "3.1.1.4", "1.234.3", "4.3.1", "4.0.0.0.0.40"]

        num = numbers[0]
        for i in range(1, len(numbers)):  # Could be micro-optimized saving split nums
            otherNum = numbers[i]

            splitNum = num.split('.')
            splitOther = otherNum.split('.')

            splits = max(len(splitNum), len(splitOther))
            for j in range(splits):
                numValue = 0
                otherValue = 0

                if j < len(splitNum):
                    numValue = int(splitNum[j])

                if j < len(splitOther):
                    otherValue = int(splitOther[j])   

                if numValue > otherValue:
                    break
                elif numValue < otherValue:
                    num = otherNum
                    break
                
                continue

        print("Highest Num: " + num)'''


        return {'FINISHED'}
    
    # Returns true if number1 is larger than number2. If less than or equal, number1 returns false
    def CompareNumberStrings(self, number1: str, number2: str) -> bool:
        splitNumber1 = number1.split('.')
        splitNumber2 = number2.split('.')

        splits = max(len(splitNumber1), len(splitNumber2))
        for j in range(splits):
            numValue = 0
            otherValue = 0

            if j < len(splitNumber1):
                numValue = int(splitNumber1[j])

            if j < len(splitNumber2):
                otherValue = int(splitNumber2[j])   

            if numValue > otherValue:
                return True
            elif numValue < otherValue:
                return False
            
            continue


    def WalkDirectory_R(self, directoryPath: str):
        for entry in os.scandir(directoryPath):
            if entry.is_dir():
                self.WalkDirectory_R(entry.path)
            
            if entry.is_file() and entry.name.endswith(".fbx"):
                fileName = ""
                match = re.match(r"([a-zA-Z\-\_]+)(\d+(?:\.\d+)*)", entry.name)
                
                if match:
                    fileName = match.group(1)
                    fileNumber = match.group(2)

                    newFileInfo = SableFileInfo(fileName, fileNumber, entry.path)
                    if fileName in self.fileNameToListDict:
                        self.fileNameToListDict[fileName].append(newFileInfo)
                    else:
                        self.fileNameToListDict[fileName] = [newFileInfo]

                    # Update latest FileInfo
                    if fileName in self.fileNameToLatestFileDict:
                        if self.CompareNumberStrings(fileNumber, self.fileNameToLatestFileDict[fileName].fileNumber):
                            self.fileNameToLatestFileDict[fileName] = newFileInfo
                    else:
                        self.fileNameToLatestFileDict[fileName] = newFileInfo

                    #sable_print("File Name: " + fileName + " File Numbers: " + fileNumber)


'''class OT_sable_import_fbx(bpy.types.Operator):
    bl_idname = "sable.import_fbx"
    bl_label = "Imports an .fbx with specific parameters and applies additional operations"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        filepath = bpy.data.filepath
        #bpy.ops.wm.open_mainfile(filepath=os.path.dirname(filepath))
        #bpy.ops.import_scene.fbx("INVOKE_DEFAULT", )
        #bpy.ops.import_scene.fbx(filepath=os.path.dirname(filepath), ignore_leaf_bones=True)
        bpy.ops.import_scene.fbx(filepath="C:\\Users\\Sable\\Desktop\\Everything\\VRChat\\SableAvatar\\Clothes\\AthleticShorts\\Exports\\AthleticShorts1.2.fbx", ignore_leaf_bones=True)
        #bpy.ops.import.open_filebrowser_sable("INVOKE_DEFAULT")
        return {"FINISHED"}'''

class VIEW3D_PT_sable_fbx_importer(bpy.types.Panel):  # class naming convention ‘CATEGORY_PT_name’

    # where to add the panel in the UI
    bl_space_type = "VIEW_3D"  # 3D Viewport area (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/space_type_items.html#rna-enum-space-type-items)
    bl_region_type = "UI"  # Sidebar region (find list of values here https://docs.blender.org/api/current/bpy_types_enum_items/region_type_items.html#rna-enum-region-type-items)

    bl_category = "Sable"  # found in the Sidebar
    bl_label = "Sable's .fbx Importer"  # found at the top of the Panel

    def draw(self, context):
        scn = context.scene
        col = self.layout.column(align=True)
        col.operator("sable.import_fbx", text="Import .fbx")
        col.separator()
        col.operator("sable.import_all", text="Import All")
        col.separator()

        col.prop(scn, 'sable_fbx_to_import')        
        col.separator()    
        col.prop(scn, 'sable_delete_vertex_groups')        
        col.separator()
        col.prop(scn, 'sable_delete_bones')        
        col.separator()        
        col.prop(scn, 'sable_import_offset')      
        col.separator()        
        col.prop(scn, 'sable_imports_to_offset')  
        col.separator()                 
        col.prop(scn, 'sable_invert_imports_to_offset')
        col.separator()                 
        col.prop(scn, 'sable_debug')

def register():
    bpy.types.Scene.sable_fbx_to_import = StringProperty(
        name='.fbxs to Import',
        description='A list of .fbxs to import and clean-up all at once! Seperated by \',\'',
        default="SableTail, HairPinned",
    )     
    
    bpy.types.Scene.sable_delete_vertex_groups = StringProperty(
        name='Delete Vertex Groups',
        description='The names of the Vertex Groups to delete from the imported model(s). Seperated by \',\'',
        default="[Delete]",
    )

    bpy.types.Scene.sable_delete_bones = StringProperty(
        name='Delete Bones',
        description='The names of the Bones and childern to delete from the imported model(s). Seperated by \',\'',
        default="",
    )

    bpy.types.Scene.sable_import_offset = FloatProperty(
        name='Import Offset',
        description='The amount of offset to apply in the +Z direction',
        default=0.008242408,
    )

    bpy.types.Scene.sable_imports_to_offset = StringProperty(
        name='Imports to offset',
        description='The names of the imported .fbxs to offset. Seperated by \',\'',
        default="AthleticShoes",
    )       

    bpy.types.Scene.sable_invert_imports_to_offset = BoolProperty(
        name='Invert Imports to Offset',
        description='The named imports to offsets, will offset any other import NOT in the sable_imports_to_offset list',
        default=True,
    )

    bpy.types.Scene.sable_debug = BoolProperty(
        name='Debug',
        description='Allow debug console print statements',
        default=False,
    )
        
    bpy.utils.register_class(VIEW3D_PT_sable_fbx_importer)  
    #bpy.utils.register_class(OT_sable_clean_up_imported_mesh)
    bpy.utils.register_class(OT_sable_import_fbx)
    bpy.utils.register_class(OT_sable_import_all)    

def unregister():
    del bpy.types.Scene.sable_fbx_to_import
    del bpy.types.Scene.sable_delete_vertex_groups
    del bpy.types.Scene.sable_delete_bones    
    del bpy.types.Scene.sable_imports_to_offset
    del bpy.types.Scene.sable_import_offset    
    del bpy.types.Scene.sable_invert_imports_to_offset    
    del bpy.types.Scene.sable_debug
    bpy.utils.unregister_class(VIEW3D_PT_sable_fbx_importer)
    #bpy.utils.unregister_class(OT_sable_clean_up_imported_mesh)
    bpy.utils.unregister_class(OT_sable_import_fbx)
    bpy.utils.unregister_class(OT_sable_import_all)    


if __name__ == "__main__":
    register()