import exifread
import pandas as pd


class Fps:
    def __init__(self, images):
        timestamps = pd.DataFrame([
            [str(exifread.process_file(open(images[i], "rb"))["Image DateTime"]),  # Times
             int(images[i].replace(".tif", "").split("-")[-1])]  # Slices
            for i in range(len(images))],
            columns=["Time", "Slice"])
        timestamps = timestamps.sort_values("Slice", ignore_index=True).copy()
        # convert timestamp into seconds, using only hh:mm:ss
        timestamps["Time"] = timestamps.Time.apply(lambda x:
                                                   int(x.split(" ")[-1].split(":")[0]) * 3600 +
                                                   int(x.split(" ")[-1].split(":")[1]) * 60 +
                                                   int(x.split(" ")[-1].split(":")[2]))

        # count fps for each second
        fps_df = timestamps.groupby("Time").size().reset_index(name="fps")
        self.start = timestamps.Time.min() + 1 - min(1, fps_df.iloc[0, 1] / fps_df.iloc[1, 1])
        # for information
        self.values = fps_df.fps.values[1:-1]
        # first and last second are not necessarily a full second; use nearest fps if higher
        if fps_df.iloc[0, 1] < fps_df.iloc[1, 1]:
            fps_df.iloc[0, 1] = fps_df.iloc[1, 1].copy()
        if fps_df.iloc[-1, 1] < fps_df.iloc[-2, 1]:
            fps_df.iloc[-1, 1] = fps_df.iloc[-2, 1].copy()

        # use fps to create a more accurate timestamp, start from 0s
        fps_series = timestamps.Time.apply(lambda x: fps_df[fps_df.Time == x].fps.sum())
        timestamps["Time"] = (fps_series.shift(1) ** (-1)).cumsum()
        timestamps.loc[0, "Time"] = 0
        # convert slice to start from 1 if not already
        timestamps.Slice = timestamps.Slice - timestamps.Slice.min() + 1

        # Dictionary slice: time
        self.time_dict = timestamps.set_index("Slice").to_dict()["Time"]
