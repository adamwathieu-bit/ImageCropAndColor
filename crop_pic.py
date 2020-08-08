import numpy as np
import argparse
import cv2
from PIL import Image, ImageDraw
import datetime
import csv
import os
import json
import json_constants as constants

MODIFIED_TIFF_TAG = "_crop"
TIFF_FOLDER_NAME = "cropped_TIFFs"
TIFF_EXTENSIONS = (".tif", ".tiff", ".TIF", ".TIFF")


CSV_FOLDER_NAME = "csv_report"
CSV_FILENAME = "report.csv"

CSV_COLUMN_NAMES = ['Original Image FileName', 'Cropped Image FileName', 'CenterX', 'CenterY', 'Radius', 'Pixels in [40,200]', 'Pixels', 'Pixel Ratio', 'time']



# Description: creates and adds folder called folder_name to directory: working_directory,
#			   returns path to folder
# ex: folder_name = "normalizedCSVs", working_directory = /path/to/directory
# return: "/path/to/directory/normalizedCSVs"
def add_folder_to_directory(folder_name, working_directory):
	new_directory = os.fsdecode(os.path.join(working_directory, folder_name))
	if not os.path.isdir(new_directory): 
		os.makedirs(new_directory)
	return new_directory

# Description: takes parameter original_filename and adds extension to name
# ex: original_filename = "helloWorld.txt", extension = "_addMe"
# return: helloWorld_addMe.txt
def make_modified_filename(original_filename, extension):
	filename_root, filename_ext = os.path.splitext(os.path.basename(original_filename))
	return filename_root + extension + filename_ext

def crop_circle(image_path, center, radius):
	img = Image.open(image_path).convert("RGB")
	np_img = np.array(img)
	h, w = img.size

	center_X = center[0]
	center_Y = center[1]

	rectangle = [center_X - radius, center_Y - radius, center_X + radius, center_Y + radius]

	# Create same size alpha layer with circle
	alpha = Image.new('L', img.size, 0)
	draw = ImageDraw.Draw(alpha)
	draw.pieslice( rectangle, start = 0, end = 360, fill=255)

	# Convert alpha Image to numpy array
	np_alpha = np.array(alpha)
	# Add alpha layer to RGB
	np_img = np.dstack((np_img, np_alpha))

	return Image.fromarray(np_img)

def save_image_to_file(img_obj, complete_file_path):
	img_obj.save(complete_file_path)

def find_circle(image_path, circle_width_buffer, hough_dp, min_dist, min_radius):
	image = cv2.imread(image_path)
	gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
	circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp = hough_dp, minDist = min_dist, minRadius = min_radius)

	if circles is not None:
		# convert the (x, y) coordinates and radius of the circles to integers
		circles = np.round(circles[0, :]).astype("int")
		# loop over the (x, y) coordinates and radius of the circles
		for count, (x, y, r) in enumerate(circles):
			if count > 1: 
				print("ERROR: Detected more than one circle in the image")
				return -1

			newR = r - circle_width_buffer

			return x, y, newR
	else: 
		print("ERROR: No circles detected.")
		return -1

def find_total_pixels_within_range(image_path, color_range):
	histSize_bin = 1
	color = ('b','g','r')
	newIm = cv2.imread(image_path, -1)

	ret, mask = cv2.threshold(newIm[:, :, 3], 0, 255, cv2.THRESH_BINARY)
	totalPixels = 0

	for i, col in enumerate(color):
		histr = cv2.calcHist([newIm],[i],mask,[histSize_bin],color_range)
		# print("histr: {}".format(histr))
		totalPixels += histr[0]

	return int(totalPixels[0])

def append_list_as_row(csv_filename, list_of_elem):
    with open(csv_filename, 'a+', newline='') as write_obj:
        csv_writer = csv.writer(write_obj)
        csv_writer.writerow(list_of_elem)

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("-config", "--configuration", required = True, help = "Path to configuration file")
	args = vars(ap.parse_args())
	json_file_path = args["configuration"]
	json_object = json.load(open(json_file_path))

	tiff_directory = str(json_object[constants.TIFF_DIRECTORY])


	# extract directory from JSON file that user wants to save cropped TIFF's to
	save_to_directory = str(json_object[constants.CROPPED_TIFF_DIRECTORY])
	# add folder called TIFF_FOLDER_NAME to save_to_directory
	save_folder = add_folder_to_directory(TIFF_FOLDER_NAME, save_to_directory)


	# extract directory from JSON file that user wants to save report to
	csv_save_directory = str(json_object[constants.CSV_SAVE_PATH])
	# add folder called CSV_FOLDER_NAME to directory
	csv_folder = add_folder_to_directory(CSV_FOLDER_NAME, csv_save_directory)
	# add csv file to the folder called CSV_FOLDER_NAME
	complete_csv_path = os.fsdecode(os.path.join(csv_folder, CSV_FILENAME))

	
	circle_min_dist = int(json_object[constants.CIRCLE_MIN_DIST])
	circle_min_radius = int(json_object[constants.CIRCLE_MIN_RADIUS])
	hough_dp = int(json_object[constants.HOUGH_DP])


	# write header row to csv report file
	with open(complete_csv_path, mode='w') as csvfileMod:
		csv_writer = csv.writer(csvfileMod, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
		csv_writer.writerow(CSV_COLUMN_NAMES)



	circle_width_buffer = 140 # offset for width of black circle
	color_range = [40, 200]
	total_range = [0,256]
	estimate = 0 # estimated seconds per job
	first_tiff_file = True


	num_pics = 0
	# count amount of tiff files in directory
	for file in os.listdir(tiff_directory):
		if file.endswith(TIFF_EXTENSIONS): 
			num_pics += 1

	time_left = 0

	for file in os.listdir(tiff_directory):
		complete_file_path = os.fsdecode(os.path.join(tiff_directory, file))
		if file.endswith(TIFF_EXTENSIONS): 
			new_tiff_filename = make_modified_filename(file, MODIFIED_TIFF_TAG)
			complete_new_tiff_path = os.fsdecode(os.path.join(save_folder, new_tiff_filename))

			print("Estimated time remaining: {}".format(str(datetime.timedelta(seconds = time_left)) if not first_tiff_file else "Calculating..."))
			print("Working on: {}".format(file))



			begin_time = datetime.datetime.now()
			centerX, centerY, radius = find_circle(complete_file_path, circle_width_buffer, hough_dp, circle_min_dist, circle_min_radius)
			cropped_image_obj = crop_circle(complete_file_path, [centerX, centerY], radius)
			save_image_to_file(cropped_image_obj, complete_new_tiff_path)

			select_pixels = find_total_pixels_within_range(complete_new_tiff_path, color_range)
			total_pixels = find_total_pixels_within_range(complete_new_tiff_path, total_range)
			end_time = datetime.datetime.now()

			

			row_contents = [complete_file_path, complete_new_tiff_path, centerX, centerY, radius, select_pixels, total_pixels, select_pixels/total_pixels, end_time - begin_time]
			append_list_as_row(complete_csv_path, row_contents)

			print("Finished: {}".format(file))

			if first_tiff_file:
				estimate = (end_time - begin_time + datetime.timedelta(seconds = 15)).total_seconds()
				time_left = num_pics * estimate
				first_tiff_file = False

			time_left -= estimate

if __name__ == '__main__':
	main()
