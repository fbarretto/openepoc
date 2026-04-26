from eeg_exp import read
from eeg_exp.lsl_outlet import make_outlet
from eeg_exp.osc_outlet import make_client, send_bundle


def main() -> None:
    outlet = make_outlet()
    osc = make_client("127.0.0.1", 9000)
    for sample in read(is_research=False):
        outlet.push_sample(sample["values"])
        send_bundle(osc, sample["values"], "/eeg")


if __name__ == "__main__":
    main()
