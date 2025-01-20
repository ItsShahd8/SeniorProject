import os
import glob
import cv2
import face_recognition
import numpy as np

class SimpleFacerec:
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.frame_resizing = 0.25  # Resize frame for faster processing

    def load_encoding_images(self, images_path):
        """
        Load encoding images from the given folder.
        """
        images_path = os.path.join(images_path, "*")  # Match all files in the folder
        image_files = glob.glob(images_path)

        print(f"Found {len(image_files)} files in {images_path}")

        self.known_face_encodings = []
        self.known_face_names = []

        for img_path in image_files:
            print(f"Processing file: {img_path}")

            # Read the image
            img = cv2.imread(img_path)
            if img is None:
                print(f"Warning: Unable to read {img_path}. Skipping this file.")
                continue

            # Convert the image to RGB
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Encode the image
            try:
                encodings = face_recognition.face_encodings(rgb_img)
                if encodings:  # Check if encoding list is not empty
                    self.known_face_encodings.append(encodings[0])
                    # Extract name from the filename
                    name = os.path.splitext(os.path.basename(img_path))[0]  # Remove file extension
                    self.known_face_names.append(name)
                    print(f"Face detected and encoded for {name}")
                else:
                    print(f"Warning: No face detected in {img_path}. Skipping this image.")
            except Exception as e:
                print(f"Error processing {img_path}: {e}")

    def detect_known_faces(self, frame):
        """
        Detect known faces in a given frame.
        """
        # Resize the frame for faster processing
        small_frame = cv2.resize(frame, (0, 0), fx=self.frame_resizing, fy=self.frame_resizing)
        # Convert the image to RGB
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Detect all face locations and encodings in the resized frame
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        face_names = []

        for face_encoding in face_encodings:
            # Compare face encodings with the known faces
            matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)

            # Find the best match for the detected face
            if matches and len(matches) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    face_names.append(self.known_face_names[best_match_index])
                else:
                    face_names.append("Unknown")
            else:
                face_names.append("Unknown")

        # Scale back face locations to the original frame size
        face_locations = np.array(face_locations) / self.frame_resizing
        return face_locations.astype(int), face_names
