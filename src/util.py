"""A collection of support functions"""
import os
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import pylab as pl
import random


def distance(xy1, xy2):
    """
    Input:
        xy1: [<X-coordinate>,<Y-coordinate>] of point 1
        xy2: [<X-coordinate>,<Y-coordinate>] of point 2
    Output: distance between points; float
    """
    x1, y1 = xy1
    x2, y2 = xy2
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def group(cells):
    """
    Input: dataframe of unsorted cells
    Output: dataframe of still unsorted cells, dataframe of grouped cells
    """
    xy1 = cells[["X", "Y"]].values.tolist()[0]  # Coordinates of the first cell in the list
    xy2 = [cells["X"], cells["Y"]]  # Coordinates of all cells
    cells["Distance"] = distance(xy1, xy2)
    my_bool = cells.groupby("Slice")["Distance"].transform(min) == cells["Distance"]
    nearest = cells[my_bool].copy()  # Unrefined group

    length = nearest.Major.quantile(0.9)  # Cell length without risking outliers
    nearest = nearest[nearest["Distance"] <= length].copy()  # Proximity filter

    xy_mean = nearest[["X", "Y"]].mean().values.tolist()  # Coordinates of the center of the unrefined group
    cells["Distance"] = distance(xy_mean, xy2)
    my_bool = cells.groupby("Slice")["Distance"].transform(min) == cells["Distance"]
    nearest = cells[my_bool].copy()

    length = nearest.Major.quantile(0.9)
    nearest = nearest[nearest["Distance"] <= length].copy()  # Proximity filter
    nearest = nearest[nearest["Major"] <= 1.3 * nearest.Major.quantile(0.5)].copy()  # Size filter

    if len(nearest) == 0:  # If grouping was unsuccessful, group initial cell as its own group
        nearest = cells[:1]

    cells = cells.drop(nearest.index).drop(columns="Distance").copy()
    nearest = nearest.drop(columns="Distance").copy()

    return cells, nearest


def load_files(path):
    """
    Input: path to directory
    Output:
        data: list of dataframes
        images: nested list of image file paths
    """
    files = num_sorted(os.listdir(path))
    files = [path + "/" + file for file in files if file.endswith(".csv")]
    data = [pd.read_csv(file) for file in files]

    images = [os.path.join(path, i) for i in os.listdir(path) if i.endswith(".tif")]
    for sub_folder in num_sorted([i.path for i in os.scandir(path) if i.is_dir()]):
        images += num_sorted([os.path.join(sub_folder, i) for i in os.listdir(sub_folder) if i.endswith(".tif")]),

    return data, images, files


def get_rms(data, score):
    # get rms of distance from 1 for groups other than -1
    rms = [score.loc[data[data.ID == int(ID)].index, ID].apply(
        lambda x:(1 - x) ** 2).mean() ** 0.5
        for ID in list(score) if int(ID) != -1]
    # return average rms between groups
    return sum(rms) / len(rms)


def get_frequency(cells):
    cells["Rotation"] = cells["Angle"].diff()
    # convert values to fit between -90 and 90 degrees e.g. 179 to -1
    cells.loc[cells.Rotation > 90, "Rotation":] += -180
    cells.loc[cells.Rotation <= -90, "Rotation":] += 180

    mode = "mean"
    if mode == "median":
        med_filter = cells.Rotation.rolling(5).median().shift(-2).copy()
        cells.loc[med_filter.notna(), "Rotation"] = med_filter[med_filter.notna()].copy()
    elif mode == "mean":
        mean_filter = cells.Rotation.rolling(5).mean().shift(-2).copy()
        cells.loc[mean_filter.notna(), "Rotation"] = mean_filter[mean_filter.notna()].copy()
    cells["Rotation_cum"] = cells.Rotation.cumsum()
    cells.iloc[0, cells.columns.get_loc("Rotation_cum")] = 0

    # convert to absolute rotation
    cells["Rotation"] = abs(cells["Rotation"])

    # convert rotation to revolutions per second
    cells["Frequency"] = cells["Rotation"] / cells["Time"].diff() / 360


def num_sorted(strings_list):
    return sorted(strings_list, key=lambda string: int("".join([char for char in string if char.isnumeric()])))


class Model:
    def __init__(self, data):
        self.features = ["X", "Y", "Major", "Minor", "Angle"]
        self.x = data[self.features]
        self.y = pd.get_dummies(data.ID.astype(str))
        self.model = RandomForestRegressor().fit(self.x, self.y)

    def predict(self, data):
        prediction = self.model.predict(data[self.features])
        prediction = pd.DataFrame(prediction, columns=list(self.y), index=data.index)
        return prediction


class Diffusion:
    """Model rotational diffusion of a free floating cell"""
    def __init__(self, data, p=0.01):
        self.angles = pl.linspace(0, pl.pi, 1001)
        self.time_step = 0.001
        viscosity = 0.00100  # water at 20C; Pa*s = N/m^2 *s
        kb = 1.38e-23  # boltzmann constant; J/K = N*m/K
        temp = 293  # K
        # Cell width and length; m
        width = pl.median([df.Minor.median() for ID, df in data.dataframe.groupby("ID") if ID != -1])*data.px_to_m
        length = pl.median([df.Major.median() for ID, df in data.dataframe.groupby("ID") if ID != -1])*data.px_to_m

        dr = (3 * kb * temp * pl.log(length / width)) / (pl.pi * viscosity * length ** 3)
        """rotational diffusion coefficient; 1/s; https://aip.scitation.org/doi/full/10.1063/1.5092958 (Eq 10)"""
        p_dist = []
        for angle in self.angles:
            p_dist += self.p_func(angle, self.time_step, dr),

        p_dist = [p/sum(p_dist) for p in p_dist]
        self.p_dist_cum = pl.cumsum(p_dist)

        results = []
        n = 500
        for i in range(n):
            results += self.rot_max(),
        log_results = pl.log(results)
        results = [pl.exp(random.gauss(float(pl.mean(log_results)), float(pl.std(log_results)))) for _ in range(10000)]
        self.result = pl.quantile(results, 1-p)

    @staticmethod
    def p_func(angle, time, dr):
        """diffusion probability distribution
        https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5453791/ (small T behavior)"""
        return 1 / pl.sqrt(4 * pl.pi * dr * time) * pl.exp(-(angle ** 2 / (4 * dr * time)))

    def step(self):
        r = random.random()
        return random.choice([-1, 1]) * self.angles[len(self.p_dist_cum[r > self.p_dist_cum])]

    def rot_max(self):
        angle_cum = 0
        time = 0
        time_max = 1
        angle_data = [angle_cum]

        while time < time_max:
            angle_cum += self.step()
            time += self.time_step
            angle_data += angle_cum,

        return max(angle_data) - min(angle_data)
