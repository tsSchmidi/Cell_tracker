from src.util import *


class Data:
    """A class to store and process data"""
    def __init__(self, my_dataframe):
        self.dataframe = my_dataframe
        self.best = my_dataframe.copy()
        self.rms = 1
        self.score = None
        self.slices = my_dataframe["Slice"].max()
        self.results = Results()
        self.start_time = None
        self.px_to_m = 0.185e-6
        self.brownian = None
        if "ID" not in list(self.dataframe):
            self.dataframe.Angle = 180 - self.dataframe.Angle
            self.dataframe["AspectRatio"] = self.dataframe.Major / self.dataframe.Minor

    def sort(self, min_coverage=0.25):
        """Perform initial proximity-based sorting"""
        print("Sorting cells...")
        cells = len(self.dataframe)
        progress_updates = [0.2, 0.4, 0.6, 0.8, 1.0]
        grouped = []
        while len(self.dataframe) > 0:
            self.dataframe, my_group = group(self.dataframe)
            grouped += my_group,
            progress = (cells - len(self.dataframe))/cells
            if progress >= progress_updates[0]:
                print(f"{int(progress_updates[0]*100)}%")
                del progress_updates[0]

        good = [df for df in grouped if len(df) >= self.slices*min_coverage]  # Coverage filter
        bad = [df for df in grouped if len(df) < self.slices*min_coverage]  # Rejects are grouped together

        bad = pd.concat(bad)
        bad.sort_values(by=" ", inplace=True)
        bad["ID"] = -1

        ids = list(range(len(good)))
        random.shuffle(ids)
        for i in range(len(good)):
            good[i]["ID"] = ids[i]

        if len(good) > 0:
            good = pd.concat(good)
            self.dataframe = pd.concat([good, bad]).copy()
        else:
            self.dataframe = bad.copy()

    def _improve(self):
        """Use machine learning to improve grouping"""
        if not self.score:
            self.predict()
        rms = get_rms(self.dataframe, self.score)
        if rms < self.rms:
            self.rms = rms
            self.best = self.dataframe.copy()

        # Create a table with 1st and 2nd best IDs as columns
        ranks = pd.DataFrame(
            self.score.columns.to_series()[self.score.apply(pl.argsort, axis=1).values[:, ::-1][:, :2]],
            index=self.score.index, columns=["1st", "2nd"])

        self.dataframe["ID"] = self.dataframe.apply(
            lambda row: int(ranks.loc[row.name, "1st"])
            if self.score.loc[row.name, ranks.loc[row.name, "1st"]] > 0.8
            or int(ranks.loc[row.name, "1st"]) != row["ID"]
            else int(ranks.loc[row.name, "2nd"]),
            axis=1)

        self.remove_distant()
        self.remove_duplicates(self.score)
        self.score = None

    def improve(self, rounds=5):
        if rounds < 1:
            return

        for i in range(rounds):
            if i == 0:
                print("Improving cell grouping...")
            self._improve()
            print(f"{int((i + 1) / rounds * 100)}%")

        self.predict()
        rms = get_rms(self.dataframe, self.score)
        if rms < self.rms:
            self.rms = rms
            self.best = self.dataframe.copy()
        # restore data that had the best rms score
        self.dataframe = self.best.copy()
        self.dataframe.sort_values(by=" ", inplace=True)

    def remove_distant(self):
        """Apply proximity filter"""
        for cell_ID in list(set(self.dataframe.ID.values)):
            if cell_ID == -1:
                continue
            subset = self.dataframe[self.dataframe.ID == cell_ID].copy()
            xy_mean = subset[["X", "Y"]].mean().values.tolist()
            subset["Distance"] = distance(xy_mean, [subset["X"], subset["Y"]])
            xy_nearest = subset.loc[subset.Distance == subset.Distance.min(), ["X", "Y"]].mean().values.tolist()
            subset["Distance"] = distance(xy_nearest, [subset["X"], subset["Y"]])
            ind = subset[subset.Distance > 1.1 * subset.Major.quantile(0.9)].index
            self.dataframe.loc[ind, "ID"] = -1

    def remove_duplicates(self, score):
        """Filter lower-scoring duplicates"""
        duplicates = self.dataframe[self.dataframe.duplicated(subset=["Slice", "ID"], keep=False)]
        duplicates = duplicates[duplicates.ID != -1].groupby(["Slice", "ID"])

        for key, item in duplicates:
            pair = duplicates.get_group(key)
            # get full score table
            score_pair = score.loc[pair.index]
            # get only the scores for their own ID
            score_pair = score_pair[[i for i in list(score_pair) if i == str(pair.ID.values[0])]]
            # get index of cell with the lower score
            ind = score_pair[score_pair.iloc[:, [0]] != score_pair.max()].dropna().index
            # change group of the loser to -1
            self.dataframe.loc[ind, "ID"] = -1

    def add_time(self, fps):
        self.dataframe["Time"] = self.dataframe.Slice.apply(lambda slc: fps.time_dict[slc])
        self.start_time = fps.start

    def predict(self):
        self.score = Model(self.dataframe).predict(self.dataframe)

    def get_results(self, brownian_1sec=1.6):
        brownian = brownian_1sec * pl.pi**pl.log10(self.dataframe.Time.max())
        for cell_ID in list(set(self.dataframe.ID.values)):
            if cell_ID == -1:
                continue

            cell_group = self.dataframe[self.dataframe.ID == cell_ID].copy()
            # calculate rotation/frequency
            get_frequency(cell_group)

            # skip cells that don't spin
            if cell_group.Rotation_cum.max() - cell_group.Rotation_cum.min() < brownian*180/pl.pi:
                continue

            self.results.time += cell_group.Time,
            self.results.rotation_cum += cell_group.Rotation_cum,

            # gather data points to be plotted together in a boxplot
            self.results.box_plot += cell_group.Frequency.dropna(),
            # gather mean non-stationary frequency to a list
            self.results.freq += cell_group.Frequency,
            self.results.freq_mean += cell_group.loc[cell_group.Frequency > 0.1, "Frequency"].mean(),
            self.results.size += cell_group.Major.quantile(0.9)*self.px_to_m,
            self.results.cells_obs += len(cell_group),
            self.results.cells_max += self.slices,

    def plot_map(self):
        pl.figure()
        pl.scatter(self.dataframe.X, self.dataframe.Y, s=3, c=self.dataframe.ID, cmap="Set1")
        pl.xlim(0, self.dataframe.X.max() * 1.02)
        pl.ylim(self.dataframe.Y.max() * 1.02, 0)
        for cell_ID in list(set(self.dataframe.ID.values)):
            if cell_ID == -1:
                continue
            pl.annotate("n=" + str(len(self.dataframe[self.dataframe.ID == cell_ID])) + "\n",
                        (self.dataframe.loc[self.dataframe.ID == cell_ID, "X"].mean(),
                         self.dataframe.loc[self.dataframe.ID == cell_ID, "Y"].mean()),
                        fontsize=8,
                        ha="center")
        pl.show()

    def plot_rotation_cum(self):
        pl.figure()
        for i in range(len(self.results.time)):
            pl.scatter(self.results.time[i], self.results.rotation_cum[i], s=3)
            pl.plot(self.results.time[i], self.results.rotation_cum[i])
        pl.show()

    def plot_boxplot(self):
        # create empty figure and axis object
        fig, ax = pl.subplots()
        # create another empty axis object with shared x axis
        ax2 = ax.twinx()

        # boxplot
        ax.boxplot(self.results.box_plot, showfliers=False)

        # overlay stuff to boxplots
        for cell_index in range(len(self.results.box_plot)):
            # individual datapoints
            y = self.results.box_plot[cell_index]
            # random jitter
            x = [random.gauss(1 + cell_index, 0.04) for _ in range(len(y))]
            ax.plot(x, y, 'k.', markersize=1)

            # add means
            ax.plot(cell_index + 0.90, self.results.freq_mean[cell_index], marker=5, color="tab:blue")
            ax.set(ylabel="Frequency (1/s)", xlabel="Individual cells")
            ax.yaxis.label.set_color("tab:blue")
            ax.tick_params(axis="y", labelcolor="tab:blue")
            pl.xticks([i + 1 for i in range(len(self.results.box_plot))],
                      ["n=" + str(self.results.cells_obs[i]) + "\n   /" + str(self.results.cells_max[i])
                       for i in range(len(self.results.box_plot))])
            ax.tick_params(axis="x", labelsize=8)

            # add cell size
            ax2.plot(cell_index + 1.1, self.results.size[cell_index]*1e6, marker=4, color="tab:red")
            ax2.set(ylabel="Cell size (um)")
            ax2.yaxis.label.set_color("tab:red")
            ax2.tick_params(axis="y", labelcolor="tab:red")

        p1, = ax.plot([1], [-1], 'k.', markersize=1)
        p2 = pl.scatter([1], [-1], marker=5, color="tab:blue")
        p3 = pl.scatter([1], [-1], marker=8, color="tab:red")
        ax.legend([p1, p2, p3],
                  ["Frequency datapoints", "Mean motile frequency", "Cell size"],
                  bbox_to_anchor=(-0.02, 1.01, 1, 1),
                  loc='lower left',
                  mode="expand",
                  handletextpad=0.05,
                  ncol=3,
                  borderaxespad=0,
                  frameon=False)

        # exclude outliers from graph
        flat_list = [item for sublist in self.results.box_plot for item in sublist]
        y_max = max(pl.quantile(flat_list, 0.99), pl.mean(flat_list) + 4 * pl.std(flat_list))

        ax.set_ylim(0, y_max)
        ax2.set_ylim(bottom=0)
        fig.suptitle("EK01 PoXeR spinning frequency RDM", fontsize=14)
        pl.show()


class Results:
    def __init__(self):
        self.box_plot = []
        self.freq = []
        self.freq_mean = []
        self.fps = []
        self.size = []
        self.cells_obs = []
        self.cells_max = []
        self.time = []
        self.rotation_cum = []
