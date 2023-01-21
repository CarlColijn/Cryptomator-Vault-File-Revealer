# Cryptomator Vault File Revealer, v2013-01-18
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




class FolderOptions:
  def __init__(self, defaultPath, type, browseTitle, OnSelectionChange):
    self.files = None
    self.foundFile = None

    self.OnSelectionChange = OnSelectionChange

    self.path = ''
    self.defaultPath = defaultPath

    self.type = type
    self.browseTitle = browseTitle

    self.editText = tk.StringVar()
    self.editText.trace('w', lambda *args: self.OnChange())


  def OnBrowse(self, parent):
    oldPath = self.editText.get()
    if len(oldPath) == 0:
      oldPath = self.defaultPath

    newPath = tk.filedialog.askdirectory(parent=parent, title=self.browseTitle, initialdir=oldPath)
    if len(newPath) > 0:
      self.editText.set(os.path.normpath(newPath))


  def OnChange(self):
    self.path = self.editText.get()
    self.files = None
    self.OnSelectionChange()




class FileOptions:
  def __init__(self, defaultPath, type, browseTitle, OnSelectionChange):
    self.OnSelectionChange = OnSelectionChange

    self.path = ''
    self.defaultPath = defaultPath

    self.type = type
    self.browseTitle = browseTitle

    self.editText = tk.StringVar()
    self.editText.trace('w', lambda *args: self.OnChange())


  def OnBrowse(self, parent):
    oldPath = self.editText.get()
    if len(oldPath) == 0:
      oldPath = self.defaultPath

    newPath = tk.filedialog.askopenfilename(parent=parent, title=self.browseTitle, initialdir=os.path.dirname(oldPath), initialfile=os.path.basename(oldPath))
    if len(newPath) > 0:
      self.editText.set(os.path.normpath(newPath))


  def OnChange(self):
    self.path = self.editText.get()
    self.OnSelectionChange()




class FolderScanThread(threading.Thread):
  def __init__(self, folderOptions):
    super().__init__()

    self.options = folderOptions

    self.mustStop = False
    self.progress = 0
    self.description = f'Scanning {folderOptions.type} folder'


  def run(self):
    self.options.files = []

    for file in pathlib.Path(self.options.path).rglob('*'):
      if self.mustStop:
        break

      self.progress += 1

      if file.is_file():
        self.options.files.append(file)




class FileFindThread(threading.Thread):
  def __init__(self, fromFileOptions, toFolderOptions):
    super().__init__()

    self.fromFileOptions = fromFileOptions
    self.toFolderOptions = toFolderOptions
    self.toFolderOptions.foundFile = None

    self.mustStop = False
    self.progress = 0
    self.description = f'Finding {toFolderOptions.type} file'


  def run(self):
    with self.DisabledFile():
      for file in self.toFolderOptions.files:
        if self.mustStop:
          break

        self.progress = self.progress + 1
        if not file.exists():
          self.toFolderOptions.foundFile = file
          break


  @contextmanager
  def DisabledFile(self):
    file = pathlib.Path(self.fromFileOptions.path)
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

    myDocumentsPath = self.GetDocumentsPath()
    self.encryptedFolderOptions = FolderOptions(myDocumentsPath, 'vault', 'Browse to the Cryptomator vault', lambda: self.OnSelectionChange())
    self.encryptedFileOptions = FileOptions(myDocumentsPath, 'vault', 'Select the encrypted file in the Cryptomator vault', lambda: self.OnSelectionChange())
    self.decryptedFolderOptions = FolderOptions(myDocumentsPath, 'unlocked', 'Browse to the unlocked folder', lambda: self.OnSelectionChange())
    self.decryptedFileOptions = FileOptions(myDocumentsPath, 'unlocked', 'Select the decrypted file in the unlocked folder', lambda: self.OnSelectionChange())

    self.fromFileOptions = self.encryptedFileOptions
    self.toFolderOptions = self.decryptedFolderOptions
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

    tk.Label(mainFrame, text='Choose:', anchor='w').pack(side=tk.TOP, pady=(20,0), anchor='w')

    actionFrame = tk.Frame(mainFrame)
    actionFrame.pack(side=tk.TOP, fill=tk.BOTH)
    self.mode = tk.IntVar(None, 1)
    tk.Radiobutton(actionFrame, text='Select file in vault,\nfind file in unlocked folder', value=1, variable=self.mode, command=self.OnEncryptedToDecrypted, indicator=0).pack(side=tk.LEFT, ipadx=7, ipady=3)
    tk.Radiobutton(actionFrame, text='Select file in unlocked folder,\nfind file in vault', value=2, variable=self.mode, command=self.OnDecryptedToEncrypted, indicator=0).pack(side=tk.LEFT, ipadx=7, ipady=3)

    browseFrame = tk.Frame(mainFrame)
    browseFrame.pack(side=tk.TOP, pady=(30,0), fill=tk.BOTH)
    self.encToDecFrame = tk.Frame(browseFrame)
    self.encToDecFrame.pack(side=tk.TOP, fill=tk.BOTH)
    tk.Label(self.encToDecFrame, text='Path of the file in the Cryptomator vault:', anchor='w').pack(side=tk.TOP, anchor='w')
    self.AddBrowseSection(self.encToDecFrame, self.encryptedFileOptions)
    tk.Label(self.encToDecFrame, text='Path of the unlocked folder:', anchor='w').pack(side=tk.TOP, anchor='w')
    self.AddBrowseSection(self.encToDecFrame, self.decryptedFolderOptions)

    self.decToEncFrame = tk.Frame(browseFrame)
    self.decToEncFrame.pack(side=tk.TOP, fill=tk.BOTH)
    tk.Label(self.decToEncFrame, text='Path of the file in the unlocked folder:', anchor='w').pack(side=tk.TOP, anchor='w')
    self.AddBrowseSection(self.decToEncFrame, self.decryptedFileOptions)
    tk.Label(self.decToEncFrame, text='Path of the Cryptomator vault:', anchor='w').pack(side=tk.TOP, anchor='w')
    self.AddBrowseSection(self.decToEncFrame, self.encryptedFolderOptions)
    self.decToEncFrame.pack_forget()

    self.findButton = tk.Button(mainFrame, text='Find unlocked file', state=tk.DISABLED, width=15, command=self.OnFindFile)
    self.findButton.pack(side=tk.TOP, pady=(10,0), ipadx=7, ipady=3, anchor='w')

    tk.Label(mainFrame, text='Result:', anchor='w').pack(side=tk.TOP, pady=(30,0), anchor='w')
    self.progressLog = ProgressLog(mainFrame, state=tk.DISABLED, height=6)
    self.progressLog.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

    self.revealButton = tk.Button(mainFrame, text='Reveal unlocked file', state=tk.DISABLED, width=15, command=self.OnRevealFile)
    self.revealButton.pack(side=tk.LEFT, anchor='w', ipadx=7, ipady=3)

    self.exitButton = tk.Button(mainFrame, text='Exit', width=7, command=self.OnExit)
    self.exitButton.pack(side=tk.RIGHT, anchor='e', pady=(30,0), ipadx=15, ipady=3)

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


  def AddBrowseSection(self, mainFrame, options):
    browseFrame = tk.Frame(mainFrame)
    browseFrame.pack(side=tk.TOP, fill=tk.BOTH)

    editBox = tk.Entry(browseFrame, textvariable=options.editText)
    editBox.pack(side=tk.LEFT, expand=True, fill=tk.X)

    browseButton = tk.Button(browseFrame, text='Browse...', command=lambda: options.OnBrowse(self))
    browseButton.pack(side=tk.RIGHT, padx=(10,0), ipadx=5, ipady=1)


  def OnEncryptedToDecrypted(self):
    self.encToDecFrame.pack(fill=tk.BOTH)
    self.decToEncFrame.pack_forget()

    self.findButton.config(text='Find unlocked file')
    self.revealButton.config(text='Reveal unlocked file')

    self.fromFileOptions = self.encryptedFileOptions
    self.toFolderOptions = self.decryptedFolderOptions


  def OnDecryptedToEncrypted(self):
    self.decToEncFrame.pack(fill=tk.BOTH)
    self.encToDecFrame.pack_forget()

    self.findButton.config(text='Find vault file')
    self.revealButton.config(text='Reveal vault file')

    self.fromFileOptions = self.decryptedFileOptions
    self.toFolderOptions = self.encryptedFolderOptions


  def OnShuttingDown(self, *args):
    if not self.scanThread is None:
      self.scanThread.mustStop = True


  def OnFindFile(self):
    if self.AllPathsExists():
      self.progressLog.Reset()
      self.revealButton['state'] = 'disable'
      self.toFolderOptions.foundFile = None

      if not self.toFolderOptions.files is None:
        self.progressLog.Log(f'Scanning {self.toFolderOptions.type}... already scanned.')
        self.progressLog.NextLine()
        self.FindMissingFile()
      else:
        self.scanThread = FolderScanThread(self.toFolderOptions)
        self.scanThread.start()
        self.MonitorThread(lambda: self.FindMissingFile())


  def OnRevealFile(self):
    self.RevealFile(self.toFolderOptions.foundFile)


  def OnExit(self):
    self.destroy()


  def OnSelectionChange(self):
    self.findButton['state'] = 'normal' if self.AllPathsEntered() else 'disable'


  def FindMissingFile(self):
    self.scanThread = FileFindThread(self.fromFileOptions, self.toFolderOptions)
    self.scanThread.start()
    self.MonitorThread(self.OnFileScanDone)


  def OnFileScanDone(self):
    self.progressLog.Log(f'Selected {self.fromFileOptions.type} file: {self.fromFileOptions.path}')
    self.progressLog.NextLine()

    foundFile = self.toFolderOptions.foundFile
    if foundFile is None:
      self.progressLog.Log(f'Found {self.toFolderOptions.type} file: sorry, file not found.')
      self.TellFileNotFound(self.toFolderOptions.type)
    else:
      self.revealButton['state'] = 'normal'
      self.progressLog.Log(f'Found {self.toFolderOptions.type} file: {foundFile}')
      self.TellFileFound(foundFile, self.toFolderOptions.type)


  def MonitorThread(self, OnScanDone):
    if self.scanThread.is_alive():
      self.progressLog.Log(f'{self.scanThread.description}... {self.scanThread.progress}')
      self.after(100, lambda: self.MonitorThread(OnScanDone))
    else:
      self.progressLog.Log(f'{self.scanThread.description}... done.')
      self.progressLog.NextLine()
      OnScanDone()


  def AllPathsEntered(self):
    return len(self.fromFileOptions.path) > 0 and len(self.toFolderOptions.path) > 0


  def AllPathsExists(self):
    selectionOK = False
    if not os.path.exists(self.fromFileOptions.path):
      tk.messagebox.showinfo('Invalid file selected', f'The {self.fromFileOptions.type} file you selected doesn\'t exist.')
    elif not os.path.exists(self.toFolderOptions.path):
      tk.messagebox.showinfo('Invalid folder selected', f'The {self.toFolderOptions.type} folder you selected doesn\'t exist.')
    else:
      selectionOK = True

    return selectionOK


  def TellFileNotFound(self, fileType):
    tk.messagebox.showinfo('File not found', f'I cannot find the corresponding {fileType} file!  Maybe you unlocked the wrong vault?')


  def TellFileFound(self, file, fileType):
    userChoice = tk.messagebox.askquestion('File found', f'The corresponding {fileType} file is:\n\n{file}\n\nDo you want to reveal this file in Explorer?')
    if userChoice == 'yes':
      self.RevealFile(file)


  def RevealFile(self, file):
    explorerPath = pathlib.Path(os.getenv('WINDIR'), 'explorer.exe')
    subprocess.run([str(explorerPath), '/select,', str(file)])




mainWindow = MainWindow()
mainWindow.mainloop()
