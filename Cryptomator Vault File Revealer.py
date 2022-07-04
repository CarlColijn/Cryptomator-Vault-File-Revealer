# Cryptomator Vault File Revealer
#
# Reveals the decrypted file which corresponds with an encrypted file
# in a locked Cryptomator vault, or the reverse.
#
# Created by Carl Colijn
# Warning: use at your own risk!
#
# Instructions and notes:
# - This script requires Python 3, as well as the following modules:
#   - wx
#   - win32com
# - This script only works on Windows; feel free to adapt it to other OSes and
#   share your result!
# - Before starting this script, unlock the vault in Cryptomator first.
# - The script works by temporarily giving the selected encrypted or decrypted
#   file another file extension.  For encrypted files the file extension is
#   then not .c9r anymore and Cryptomator doesn't recognize it any longer as a
#   vault file, causing it's matching decrypted file to disappear.  When a
#   decrypted file is renamed, it's matching encrypted file disappears while a
#   new encrypted file will be created.  The script creates a folder listing
#   of both the unlocked and locked vault folders, so that it can detect which
#   file disappears where when it renames the encrypted or decrypted file.
# - Might something go wrong: the selected encrypted and decrypted files are
#   just given another extension by adding '.cvfr-sidestepped' to the file
#   name.  So if the script fails and doesn't restore a decrypted or encrypted
#   file anymore, find the renamed file and manually rename it back to what it
#   should be named (just remove the added extension).
# - IMPORTANT NOTE: for revealing decrypted files I only tested this script on
#   regular encrypted file entries, and not on encrypted folder entries.
#   Renaming those seems rather iffy to me; will Cryptomator handle that
#   silently without issue, or could it mess up the vault structure in such a
#   way that the vault gets corrupted?  I've not felt the need to find out
#   yet :)  Feel free to find out at your own risk and tell us the result!

from win32com.shell import shell, shellcon
import os
import wx
import subprocess
import pathlib
from contextlib import contextmanager


def GetDocumentsPath():
  return shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)


def BrowseFolder(defaultPath, prompt):
  browseDlg = wx.DirDialog(None, prompt, defaultPath=defaultPath, style=wx.DD_DEFAULT_STYLE)
  if browseDlg.ShowModal() == wx.ID_OK:
    result = browseDlg.GetPath()
  else:
    result = None
  browseDlg.Destroy()
  return result


def BrowseFile(defaultPath, prompt):
  browseDlg = wx.FileDialog(None, prompt, defaultDir=defaultPath, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
  if browseDlg.ShowModal() == wx.ID_OK:
    result = pathlib.Path(browseDlg.GetPath())
  else:
    result = None
  browseDlg.Destroy()
  return result


def GetFilesInFolder(folderPath):
  return [file for file in pathlib.Path(folderPath).rglob('*') if file.is_file()]


@contextmanager
def DisableFile(file):
  tempFile = file.with_name(file.name + '.cvfr-sidestepped')
  try:
    file.rename(tempFile)
    yield
  finally:
    if tempFile.exists():
      tempFile.rename(file)


def TellFileNotFound(isEncryptedFile):
  dlg = wx.MessageDialog(None, 'I cannot find the corresponding ' + ('encrypted' if isEncryptedFile else 'decrypted') + ' file!  Maybe you unlocked the wrong vault?', 'File not found', wx.OK | wx.ICON_INFORMATION)
  dlg.ShowModal()
  dlg.Destroy()


def TellFileFound(file, isEncryptedFile):
  dlg = wx.MessageDialog(None, 'The corresponding ' + ('encrypted' if isEncryptedFile else 'decrypted') + ' file is:\n' + str(file) + '\n\nDo you want to reveal this file in Explorer?', 'File found', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION)
  if dlg.ShowModal() == wx.ID_YES:
    explorerPath = pathlib.Path(os.getenv('WINDIR'), 'explorer.exe')
    subprocess.run([str(explorerPath), '/select,', str(file)])
  dlg.Destroy()


def AskFindOtherFile():
  dlg = wx.MessageDialog(None, 'Do you want to reveal another file?', 'Reveal another', wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
  yesClicked = dlg.ShowModal() == wx.ID_YES
  dlg.Destroy()
  return yesClicked


# returns (bool: okClicked, bool: decToEncrypted)
def AskFileType():
  dlg = wx.SingleChoiceDialog(None, 'Which file do you want to reveal?', 'Reveal encrypted or decrypted file', ['Select decrypted file, reveal encrypted file', 'Select encrypted file, reveal decrypted file'], wx.OK | wx.CANCEL_DEFAULT | wx.ICON_QUESTION)
  dlg.SetSelection(0)
  okClicked = dlg.ShowModal() == wx.ID_OK
  decToEncrypted = dlg.GetSelection() == 0
  dlg.Destroy()
  return (okClicked, decToEncrypted)


def FindMissingFile(files):
  for file in files:
    if not file.exists():
      return file
  return None


def RevealEncryptedFile(encryptedFiles, decryptedFile):
  encryptedFile = None

  with DisableFile(decryptedFile):
    encryptedFile = FindMissingFile(encryptedFiles)

  if encryptedFile is None:
    TellFileNotFound(True)
  else:
    TellFileFound(encryptedFile, True)


def RevealDecryptedFile(decryptedFiles, encryptedFile):
  decryptedFile = None

  with DisableFile(encryptedFile):
    decryptedFile = FindMissingFile(decryptedFiles)

  if decryptedFile is None:
    TellFileNotFound(False)
  else:
    TellFileFound(decryptedFile, False)


class MyApp(wx.App):
  def OnInit(self):
    documentsPath = GetDocumentsPath()

    encryptedFolderPath = BrowseFolder(documentsPath, 'Browse to the locked Cryptomator vault folder')
    if encryptedFolderPath is None:
      return True
    encryptedFiles = GetFilesInFolder(encryptedFolderPath)

    decryptedFolderPath = BrowseFolder(documentsPath, 'Unlock the vault in Cryptomator and browse to the unlocked folder')
    if decryptedFolderPath is None:
      return True
    decryptedFiles = GetFilesInFolder(decryptedFolderPath)

    while True:
      (okClicked, decToEncrypted) = AskFileType()
      if not okClicked:
        return True

      if decToEncrypted:
        decryptedFile = BrowseFile(decryptedFolderPath, 'Select the decrypted file in the unlocked vault folder')
        if decryptedFile is None:
          return True
        RevealEncryptedFile(encryptedFiles, decryptedFile)
      else:
        encryptedFile = BrowseFile(encryptedFolderPath, 'Select the encrypted file in the locked vault folder')
        if encryptedFile is None:
          return True
        RevealDecryptedFile(decryptedFiles, encryptedFile)

      if not AskFindOtherFile():
        return True


app = MyApp(0)
app.MainLoop()
