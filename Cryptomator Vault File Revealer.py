# Cryptomator Vault File Revealer, v2013-01-15
#
# Reveals the decrypted file which corresponds with an encrypted file
# in a locked Cryptomator vault, or the reverse.
#
# Created by Carl Colijn
# Warning: use at your own risk!
#
# Instructions and notes:
# - This script requires Python 3, as well as the following modules:
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
import tkinter as tk
import tkinter.messagebox
import tkinter.filedialog
import tkinter.font
import tkinter.scrolledtext
import subprocess
import pathlib
import threading
from contextlib import contextmanager




class FileSet:
  def __init__(self, folderType, fileType, browseFolderTitle, browseFileTitle):
    self.folderPath = ''
    self.files = None

    self.folderType = folderType
    self.fileType = fileType
    self.browseFolderTitle = browseFolderTitle
    self.browseFileTitle = browseFileTitle

    self.editText = tk.StringVar()




class FolderScanThread(threading.Thread):
  def __init__(self, fileSet):
    super().__init__()

    self.fileSet = fileSet

    self.mustStop = False
    self.progress = 0
    self.description = f'Scanning {fileSet.folderType}'


  def run(self):
    self.fileSet.files = []

    for file in pathlib.Path(self.fileSet.folderPath).rglob('*'):
      if self.mustStop:
        break

      self.progress += 1

      if file.is_file():
        self.fileSet.files.append(file)




class FileFindThread(threading.Thread):
  def __init__(self, disableFilePath, selectFromFileSet, findInFileSet):
    super().__init__()

    self.disableFilePath = disableFilePath
    self.selectFromFileSet = selectFromFileSet
    self.findInFileSet = findInFileSet
    self.foundFile = None

    self.mustStop = False
    self.progress = 0
    self.description = f'Finding {findInFileSet.fileType}'


  def run(self):
    with self.DisableFile():
      for file in self.findInFileSet.files:
        if self.mustStop:
          break

        self.progress = self.progress + 1
        if not file.exists():
          self.foundFile = file
          break


  @contextmanager
  def DisableFile(self):
    file = pathlib.Path(self.disableFilePath)
    tempFile = file.with_name(file.name + '.cvfr-sidestepped')
    try:
      file.rename(tempFile)
      yield
    finally:
      if tempFile.exists():
        tempFile.rename(file)




class ProgressLog(tk.scrolledtext.ScrolledText):
  def __init__(self, parent, **kwargs):
    super().__init__(parent, **kwargs)

    self.currentLine = 1


  def Reset(self):
    self.config(state=tk.NORMAL)
    self.delete('1.0', tk.END)
    self.config(state=tk.DISABLED)
    self.currentLine = 1


  def Log(self, text):
    self.config(state=tk.NORMAL)
    self.delete(f'{self.currentLine}.0', f'{self.currentLine}.end')
    self.insert(f'{self.currentLine}.0', text)
    self.config(state=tk.DISABLED)


  def NextLine(self):
    self.config(state=tk.NORMAL)
    self.insert(tk.END, '\n')
    self.config(state=tk.DISABLED)
    self.currentLine += 1




class MainWindow(tk.Tk):
  def __init__(self):
    super().__init__()

    self.myDocumentsPath = self.GetDocumentsPath()
    self.scanThread = None

    self.SetupGUI()

    self.CenterOnDesktop()


  def SetupGUI(self):
    defaultFont = tk.font.nametofont('TkDefaultFont')
    bigFont = defaultFont.copy()
    bigFontSize = int(bigFont.cget('size') * 1.3)
    bigFont.config(size=bigFontSize, weight='bold')

    self.title('Cryptomator Vault File Revealer')

    mainFrame = tk.Frame(self)
    mainFrame.pack(side=tk.TOP, expand=True, fill=tk.BOTH, padx=20, pady=20)

    tk.Label(mainFrame, text='Don\'t forget to unlock the vault in Cryptomator!', font=bigFont, anchor='w').pack(side=tk.TOP, anchor='w')

    tk.Label(mainFrame, text='Path of the Cryptomator vault:', anchor='w').pack(side=tk.TOP, pady=(20,0), anchor='w')

    self.encryptedFileSet = FileSet('vault folder', 'vault file', 'Browse to the Cryptomator vault', 'Select the encrypted file in the Cryptomator vault')
    self.AddBrowseSection(mainFrame, self.encryptedFileSet)

    tk.Label(mainFrame, text='Path of the unlocked folder:', anchor='w').pack(side=tk.TOP, anchor='w')

    self.decryptedFileSet = FileSet('unlocked folder', 'unlocked file', 'Browse to the unlocked folder', 'Select the decrypted file in the unlocked folder')
    self.AddBrowseSection(mainFrame, self.decryptedFileSet)

    tk.Label(mainFrame, text='Reveal one or more files', font=bigFont).pack(side=tk.TOP, pady=(20,0), anchor='w')
    actionFrame = tk.Frame(mainFrame)
    actionFrame.pack(side=tk.TOP, fill=tk.BOTH)
    tk.Button(actionFrame, text='Select file in vault,\nreveal file in unlocked folder', command=lambda: self.EnsureFilesScanned(self.OnRevealDecryptedFile)).pack(side=tk.LEFT, ipadx=7, ipady=3)
    tk.Button(actionFrame, text='Select file in unlocked folder,\nreveal file in vault', command=lambda: self.EnsureFilesScanned(self.OnRevealEncryptedFile)).pack(side=tk.RIGHT, padx=(10,0), ipadx=7, ipady=3)
    self.progressLog = ProgressLog(mainFrame, state=tk.DISABLED, height=7)
    self.progressLog.pack(side=tk.TOP, expand=True, fill=tk.BOTH, pady=(10,0))

    tk.Button(mainFrame, text='Exit', command=self.OnExit).pack(side=tk.RIGHT, anchor='w', pady=(20,0), ipadx=15, ipady=3)

    self.bind('<Destroy>', self.OnShuttingDown)


  def CenterOnDesktop(self):
    self.update_idletasks()

    desktopWidth = self.winfo_screenwidth()
    desktopHeight = self.winfo_screenheight()
    ourWidth = self.winfo_reqwidth()
    ourHeight = self.winfo_reqheight()

    left = int((desktopWidth - ourWidth) / 2)
    top = int((desktopHeight - ourHeight) / 2)
    self.geometry(f'+{left}+{top}')
    self.minsize(ourWidth, ourHeight)


  def GetDocumentsPath(self):
    return shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)


  def AddBrowseSection(self, mainFrame, fileSet):
    browseFrame = tk.Frame(mainFrame)
    browseFrame.pack(side=tk.TOP, fill=tk.BOTH)

    fileSet.editText.trace('w', lambda *args: self.OnBrowseEntryChanged(fileSet))
    editBox = tk.Entry(browseFrame, textvariable=fileSet.editText)
    editBox.pack(side=tk.LEFT, expand=True, fill=tk.X)

    browseButton = tk.Button(browseFrame, text='Browse...', command=lambda: self.OnBrowseFolder(fileSet))
    browseButton.pack(side=tk.RIGHT, padx=(10,0), ipadx=5, ipady=1)


  def OnShuttingDown(self, *args):
    if not self.scanThread is None:
      self.scanThread.mustStop = True


  def OnBrowseEntryChanged(self, fileSet):
    newFolderPath = fileSet.editText.get()
    fileSet.folderPath = newFolderPath
    fileSet.files = None


  def OnBrowseFolder(self, fileSet):
    oldFolderPath = fileSet.editText.get()
    if len(oldFolderPath) == 0:
      oldFolderPath = self.myDocumentsPath

    newFolderPath = tk.filedialog.askdirectory(parent=self, title=fileSet.browseFolderTitle, initialdir=oldFolderPath)
    newFolderPath = os.path.normpath(newFolderPath)

    if len(newFolderPath) > 0:
      fileSet.editText.set(newFolderPath)


  def FindMissingFile(self, selectedFilePath, selectFromFileSet, findInFileSet):
    self.scanThread = FileFindThread(selectedFilePath, selectFromFileSet, findInFileSet)
    self.scanThread.start()
    self.MonitorThread(self.OnFileScanDone)


  def OnFileScanDone(self):
    self.progressLog.Log(f'Selected {self.scanThread.selectFromFileSet.fileType}: {self.scanThread.disableFilePath}')
    self.progressLog.NextLine()

    foundFile = self.scanThread.foundFile
    if foundFile is None:
      self.progressLog.Log(f'Found {self.scanThread.findInFileSet.fileType}: sorry, file not found.')
      self.TellFileNotFound(self.scanThread.findInFileSet.fileType)
    else:
      self.progressLog.Log(f'Found {self.scanThread.findInFileSet.fileType}: {foundFile}')
      self.TellFileFound(foundFile, self.scanThread.findInFileSet.fileType)


  def RevealFile(self, selectFromFileSet, findInFileSet):
    selectedFilePath = self.BrowseFile(selectFromFileSet.folderPath, selectFromFileSet.browseFileTitle)
    if len(selectedFilePath) > 0:
      self.FindMissingFile(selectedFilePath, selectFromFileSet, findInFileSet)


  def OnRevealDecryptedFile(self):
    self.RevealFile(self.encryptedFileSet, self.decryptedFileSet)


  def OnRevealEncryptedFile(self):
    self.RevealFile(self.decryptedFileSet, self.encryptedFileSet)


  def OnExit(self):
    self.destroy()


  def EnsureFileSetScanned(self, fileSet, OnScanDone):
    if not fileSet.files is None:
      self.progressLog.Log(f'Scanning {fileSet.folderType}... already scanned.')
      self.progressLog.NextLine()
      OnScanDone()
    elif os.path.exists(fileSet.folderPath):
      self.scanThread = FolderScanThread(fileSet)
      self.scanThread.start()
      self.MonitorThread(OnScanDone)
    else:
      tk.messagebox.showerror('Folder not found', f'I cannot find the specified {fileSet.folderType} folder!  Please ensure you entered the correct path, or browse to it to be sure.')


  def EnsureFilesScanned(self, OnScanDone):
    self.progressLog.Reset()
    self.EnsureFileSetScanned(self.encryptedFileSet, lambda: self.EnsureFileSetScanned(self.decryptedFileSet, OnScanDone))


  def MonitorThread(self, OnScanDone):
    if self.scanThread.is_alive():
      self.progressLog.Log(f'{self.scanThread.description}... {self.scanThread.progress}')
      self.after(100, lambda: self.MonitorThread(OnScanDone))
    else:
      self.progressLog.Log(f'{self.scanThread.description}... done.')
      self.progressLog.NextLine()
      OnScanDone()


  def BrowseFile(self, defaultPath, prompt):
    newFilePath = tk.filedialog.askopenfilename(parent=self, title=prompt, initialdir=defaultPath)
    return os.path.normpath(newFilePath)


  def TellFileNotFound(self, fileType):
    tk.messagebox.showinfo('File not found', f'I cannot find the corresponding {fileType}!  Maybe you unlocked the wrong vault?')


  def TellFileFound(self, file, fileType):
    userChoice = tk.messagebox.askquestion('File found', f'The corresponding {fileType} is:\n{file}\n\nDo you want to reveal this file in Explorer?')
    if userChoice == 'yes':
      explorerPath = pathlib.Path(os.getenv('WINDIR'), 'explorer.exe')
      subprocess.run([str(explorerPath), '/select,', str(file)])




mainWindow = MainWindow()
mainWindow.mainloop()
