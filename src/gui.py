from tkinter import *
from tkinter import filedialog as fd
from src.data import *
from src.getfps import *


def plot_freq_together(data_list):
    stamp1 = data_list[0].start_time
    ratios = [data.dataframe.Time.max() - data.dataframe.Time.min() for data in data_list]
    time_span = sum(ratios)
    interval = round(time_span/8, 0) if time_span >= 8 else 1 / round(8/time_span)
    fig, ax = pl.subplots(1, len(data_list), gridspec_kw={"width_ratios": ratios})
    for i, data in enumerate(data_list):
        stamp2 = data.start_time
        dt = stamp2 - stamp1
        for cell_ind in range(len(data.results.time)):
            times = data.results.time[cell_ind]+dt
            ax[i].scatter(times, data.results.freq[cell_ind], s=3)
            x_ticks = pl.arange(int(dt/interval)*interval, dt+ratios[i], interval)
            ax[i].set_xticks([tick for tick in x_ticks if times.min() <= tick < times.max()])
        if i != 0:
            ax[i].spines["left"].set_visible(False)
            ax[i].set_yticks([])
        if i < len(data_list) - 1:
            ax[i].spines["right"].set_visible(False)
    pl.subplots_adjust(wspace=0.1)
    flat_list = [item for data in data_list for sublist in data.results.freq for item in sublist.dropna().values]
    pl.setp(ax, ylim=(0, pl.quantile(flat_list, 0.98)))
    pl.show()


def main():
    root = Tk()
    root.withdraw()
    print("Select folder to extract csv files from.")
    path = fd.askdirectory()
    root.destroy()

    data_list, images_list, file_list = load_files(path)

    for data_ind, data in enumerate(data_list):

        print(f"Processing sample {data_ind+1} of {len(data_list)}")
        data = Data(data)
        data_list[data_ind] = data
        fps = Fps(images_list[data_ind])
        export_file = file_list[data_ind]

        data.add_time(fps)
        data.results.fps += list(fps.values)
        # data.sort()

        data.improve(rounds=0)
        data.get_results(Diffusion(data).result)

        # data.dataframe.to_csv(export_file, index=False)

    plot_freq_together(data_list)


main()
