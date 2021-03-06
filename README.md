# Practical sessions on mobile robot behavior programming

This page describes how to set up and run a practical session. We assume that your computer has been booted on the Linux Ubuntu operating system (available in the classroom). If your are currently on Windows, you have to restart your machine to boot on Ubuntu instead.

- [Download the practical session archive](https://drive.google.com/file/d/1UvSy_oyVHxMbSX-0uofcrnynYHCgtvCI/view?usp=sharing) and save it in `Documents`.
- Once the download is completed, open the file manager by clicking on the icon that looks like a folder in the menu vertical bar on the left of the desktop. Go in `Documents` and extract the archive (`Right click` -> `Extract here`). This will create a folder called `sdic2019`. You can then delete the archive file (`sdic2019.zip`).
- Download the [V-REP simulator](https://drive.google.com/file/d/1U_S2gFKWA0DkSAjmB65YWlM664h6C1hx/view?usp=sharing) (this is slightly modified version which allows to control multiple robots at the same time). and save it in `Documents/sdic2019`.
- Once the download is completed, open the file manager, go in `Documents/sdic2019` and extract the archive called `V-REP_PRO_EDU_V3_6_0_Ubuntu18_04.zip`. You can then delete the archive file.
- Open a terminal (the `$_` icon on the left pane of your desktop). Enter the two following commands to start the simulator (press `Enter` to execute):
```
cd Documents/sdic2019/V-REP_PRO_EDU_V3_6_0_Ubuntu18_04
./vrep.sh
```
- Once the simulator is open, launch `jupyter notebook` by opening another terminal (middle-click on the `$_` icon) and executing:
```
cd Documents/sdic2019/pyvrep_epuck/notebooks/
jupyter notebook
```
- This will open a web page in the browser with a list of files. Click on the practical session you want to do (`practical_session_1.ipynb` if it is the first class). This will open a document in a new tab in your browser.

The rest of the session is described in this freshly opened document, please continue from there. 
