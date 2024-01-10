// User selects folder and file type
#@ File (label = "Sample Folder", style = "directory") sampleFolder
#@ String (label = "File suffix", value = ".tif") suffix
#@ Boolean (label = "Save results", value = true) saveResults
#@ Boolean (label = "Manual threshold", value = false) manual
#@ Boolean (label = "Dark background", value = false) dark

// Suppress most windows from opening
setBatchMode(true);

// Execute the macro
processFolder(sampleFolder);

// Function to scan folders/subfolders/files to find files with correct suffix
function processFolder(currentFolder) {
	
	// List files in folder and sort them
	list = getFileList(currentFolder);
	list = Array.sort(list);
	
	// Loop through files; if folder, perform this function from start
	for (i = 0; i < list.length; i++) {
		if(File.isDirectory(currentFolder + File.separator + list[i]))
			processFolder(currentFolder + File.separator + list[i]);
	}
	
	// Count the number of image files and identify first image
	files = 0;
	strings = newArray();
	//first = 1e99;
	for (i = 0; i < list.length; i++) {
		if(endsWith(list[i], suffix)){
			files = files + 1;
			n = split(list[i],"-."); // "Asd-1.tif" => ["Asd", "1", "tif"]
			n = n[n.length - 2]; // ["Asd", "1", "tif"] => "1"
			n = parseInt(n); // "1" => 1
			strings = Array.concat(strings,n);
			//if(n < first){
				//first = n;
			
			//}
		}
	strings = Array.sort(strings);
	}
	
	// Get the name of the first image file and process all files in folder
	for (i = 0; i < list.length; i++) {
		if(endsWith(list[i], suffix)){
			first = unique(strings);
			processFiles(currentFolder, first, files, list[i]);
			i = 1e99; // Break loop
		}
	}
}

// Process image stack
function processFiles(currentFolder, first, files, file) {

	// Make sure we get a clean start
	run("Clear Results");
	roiManager("reset");

	// Open <first> file and create stack of <files> images
	currentFolder = split(currentFolder,"/");
	currentFolder = currentFolder[0];
	path = currentFolder + File.separator + file;
	run("Bio-Formats Importer", "open=[" + path + "] color_mode=Default group_files rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT use_virtual_stack dimensions axis_1_number_of_images=" + files + " axis_1_axis_first_image=" + first + " axis_1_axis_increment=1 contains=[] name=[asdasdf]");
	
	// Get title so can select the original window for measurement
	title = getTitle();

	// Create a working image for creating ROI's
	run("Duplicate...", "duplicate");

	// Reduce noise
	//run("Gaussian Blur...", "sigma=1 stack");
	run("Despeckle", "stack");

	// Enable manual threshold setting/inspection if desired
	if(manual){
		setBatchMode("show");
		if(dark){
			setAutoThreshold("Default dark");
		} else {
			setAutoThreshold("Default");
		}
		run("Threshold...");
		waitForUser("Set threshold, apply and click OK on the window that opens and then on this window");
		setBatchMode("hide");
	}

	// Convert to a binary image
	if(manual){
		
	} else if(dark){
		run("Convert to Mask", "method=Default background=Dark calculate black");
	} else {
		run("Convert to Mask", "method=Default background=Light calculate black");
	}

	// Create ROI's
	run("Analyze Particles...", "size=50-200 pixel circularity=0.00-0.80 exclude add stack");

	// Close threshold if it was opened
	if(manual){
		selectWindow("Threshold");
		run("Close");
	}
	
	// Measure various stuff from ROI's from the original image
	selectWindow(title);
	roiManager("Measure");

	if(saveResults){
		// Save results in parent folder
		folder = File.getName(currentFolder);
		filename = sampleFolder + File.separator + "Results_" + folder + ".csv";
		saveAs("Results", filename);

	} else {
		waitForUser("Press OK to close results and continue");
	}
	
	// Close results window
	selectWindow("Results");
	run("Close");
}

function unique(strings){
	same = 0;
	for (i = 0; i < lengthOf(strings[0]); i++) {
		yes = 1;
		for (item = 1; item < strings.length; item++) {
			sub = substring(strings[0],0,i+1);
			yes = yes*startsWith(strings[item],sub);
		}
		same = same + yes;
	return substring(strings[0],same);