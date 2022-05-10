# Cryptomator Vault File Revealer
#
# Reveals the decrypted file which corresponds with an encrypted file
# in a locked Cryptomator vault.
#
# Created by Carl Colijn
# Warning: use at your own risk!
#
# Instructions and notes:
# - This script requires Python 3, as well as the following modules:
#   - wx
#   - win32com
# - This script only works on Windows; feel free to adapt it to other
#   OSes and share your result!
# - Before starting this script, unlock the vault in Cryptomator first.
# - The script works by temporarily moving the selected encrypted file
#   to the side so that Cryptomator doesn't recognize it anymore.  The
#   script does a dir dump on the unlocked vault both before and after
#   moving the encrypted file; the difference in the dumps is the file
#   which was moved aside in the encrypted vault.
# - Might something go wrong: the encrypted file is not moved to another
#   location, but it is renamed by adding the extension '.cvfr-sidestepped'
#   to it.  This makes Crytpomator not recognize the file anymore, which
#   makes it disappear from the unlocked vault.  So if the script fails
#   and doesn't restore the encrypted file anymore, find the renamed file
#   and manually rename it back to what it should be named (remove the
#   added extension).
# - IMPORTANT NOTE: I only tested it on regular encrypted file entries,
#   and not on encrypted folder entries.  Renaming those seems rather iffy
#   to me; will Cryptomator handle that silently without issue, or could
#   it mess up the vault structure in such a way that the vault gets
#   corrupted?  I've not felt the need to find out yet :)  Feel free to
#   find out at your own risk and tell us the result!

from win32com.shell import shell, shellcon
import os
import wx
import subprocess


def GetDocumentsPath():
  return shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)


def BrowseDecryptedFolder(defaultPath):
  browseDlg = wx.DirDialog(None, 'Unlock the vault in Cryptomator and browse to the unlocked folder', defaultPath=defaultPath, style=wx.DD_DEFAULT_STYLE)
  if browseDlg.ShowModal() == wx.ID_OK:
    result = browseDlg.GetPath()
  else:
    result = None
  browseDlg.Destroy()
  return result


def BrowseEncryptedFile(defaultPath):
  browseDlg = wx.FileDialog(None, 'Select the encrypted file in the locked vault folder', defaultDir=defaultPath, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
  if browseDlg.ShowModal() == wx.ID_OK:
    result = browseDlg.GetPath()
  else:
    result = None
  browseDlg.Destroy()
  return result


def GetFilePathsInFolder(folderPath):
  filePaths = set()
  for rootFolderPath, folderNames, fileNames in os.walk(folderPath):
    for fileName in fileNames:
      filePaths.add(os.path.join(rootFolderPath, fileName))
  return filePaths


def DisableEncryptedFile(encryptedFilePath):
  tempFilePath = encryptedFilePath + '.cvfr-sidestepped'
  os.rename(encryptedFilePath, tempFilePath)
  return tempFilePath


def EnableEncryptedFile(tempFilePath, encryptedFilePath):
  os.rename(tempFilePath, encryptedFilePath)


def TellFileNotFound():
  dlg = wx.MessageDialog(None, 'I cannot find the corresponding decrypted file!  Maybe you unlocked the wrong vault?', 'File not found', wx.OK | wx.ICON_INFORMATION)
  dlg.ShowModal()
  dlg.Destroy()


def TellFileFound(decryptedFilePath):
  dlg = wx.MessageDialog(None, 'The corresponding decrypted file is:\n' + decryptedFilePath + '\n\nDo you want to reveal this file in Explorer?', 'File found', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION)
  result = dlg.ShowModal()
  dlg.Destroy()
  if result == wx.ID_YES:
    explorerPath = os.path.join(os.getenv('WINDIR'), 'explorer.exe')
    subprocess.run([explorerPath, '/select,', decryptedFilePath])


def AskFindOtherFile():
  dlg = wx.MessageDialog(None, 'Do you want to reveal another file?', 'Reveal another', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
  result = dlg.ShowModal()
  dlg.Destroy()
  return result == wx.ID_YES


def FindMissingFile(decryptedFolderPath, allFilePaths):
  for filePath in allFilePaths:
    if not os.path.isfile(filePath):
      return filePath
  return None


def RevealDecryptedFile(allFilePaths, decryptedFolderPath, encryptedFilePath):
  tempFilePath = DisableEncryptedFile(encryptedFilePath)
  try:
    decryptedFilePath = FindMissingFile(decryptedFolderPath, allFilePaths)
  finally:
    EnableEncryptedFile(tempFilePath, encryptedFilePath)

  if decryptedFilePath is None:
    TellFileNotFound()
  else:
    TellFileFound(decryptedFilePath)


class MyApp(wx.App):
  def OnInit(self):
    startPath = GetDocumentsPath()

    decryptedFolderPath = BrowseDecryptedFolder(startPath)
    if decryptedFolderPath is None:
      return True

    allFilePaths = GetFilePathsInFolder(decryptedFolderPath)

    while True:
      encryptedFilePath = BrowseEncryptedFile(startPath)
      if encryptedFilePath is None:
        return True

      RevealDecryptedFile(allFilePaths, decryptedFolderPath, encryptedFilePath)

      if not AskFindOtherFile():
        return True


app = MyApp(0)
app.MainLoop()
