import cv2
from simple_facerec import SimpleFacerec

# Encode faces from a folder
sfr = SimpleFacerec()
sfr.load_encoding_images("InData/")

# Load Camera
cap = cv2.VideoCapture(0)  # Change index to 0 for default camera

if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

while True:
    ret, frame = cap.read()

    if not ret or frame is None:
        print("Warning: Empty frame captured. Skipping...")
        continue

    # Detect Faces
    face_locations, face_names = sfr.detect_known_faces(frame)
    for face_loc, name in zip(face_locations, face_names):
        y1, x2, y2, x1 = face_loc[0], face_loc[1], face_loc[2], face_loc[3]

        cv2.putText(frame, name, (x1, y1 - 10), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 200), 2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 200), 4)

    cv2.imshow("Frame", frame)

    key = cv2.waitKey(1)
    if key == 27:  # Press 'ESC' to exit
        break

cap.release()
cv2.destroyAllWindows()