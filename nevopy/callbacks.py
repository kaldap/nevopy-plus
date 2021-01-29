# MIT License
#
# Copyright (c) 2020 Gabriel Nogueira (Talendar)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ==============================================================================

""" Defines a base interface for all callbacks and implements simple callbacks.

In the context of :mod:`nevopy.neat`, callbacks are utilities called at certain
points during the evolution of a population. They are a powerful tool to
customize the behavior of an evolutionary session of the NEAT algorithm.

Example:

    To implement your own callback, simply create a class that inherits from
    :class:`.Callback` and pass an instance of it to
    :meth:`.neat.population.NeatPopulation.evolve()`.

    .. code-block:: python

        class MyCallback(Callback):
            def on_generation_start(self,
                                    current_generation,
                                    max_generations):
                print("This is printed at the start of every generation!")
                print(f"Starting generation {current_generation} of "
                      f"{max_generations}.")

        pop.evolve(generations=100,
                   fitness_function=my_func,
                   callbacks=[MyCallback()])
"""

from typing import Optional, List, Dict, Union, Tuple, Callable, Any
from abc import ABC

import nevopy
from nevopy import utils

import matplotlib.pyplot as plt
from columnar import columnar
from click import style
from timeit import default_timer as timer


class Callback(ABC):
    """ Abstract base class used to build new callbacks.

    This class defines the general structure of the callbacks used by `NEvoPY's`
    neuroevolution algorithms.

    Attributes:
        population (Population): Reference to the instance of a subclass of
            :class:`.neat.population.Population` being evolved by one of
            `NEvoPY's` neuroevolution algorithm.
    """

    def __init__(self) -> None:
        self.population = None \
            # type: Optional["nevopy.base_population.Population"]

    def on_generation_start(self,
                            current_generation: int,
                            max_generations: int,
                            **kwargs) -> None:
        """ Called at the beginning of each new generation.

        Subclasses should override this method for any actions to run.

        Args:
            current_generation (int): Number of the current generation.
            max_generations (int): Maximum number of generations.
        """

    def on_fitness_calculated(self,
                              best_fitness: float,
                              avg_fitness: float,
                              **kwargs) -> None:
        """ Called right after the fitness of the population's genomes and the
        maximum number of hidden nodes and hidden connections in the population
        are calculated.

        Subclasses should override this method for any actions to run.

        Args:
            best_genome (NeatGenome): The most fit genome of the generation.
            max_hidden_nodes (int): Maximum number of hidden nodes found in a
                genome in the population.
            max_hidden_connections (int): Maximum number of hidden connections
                (connections involving at least one hidden node) found in a
                genome in the population.
        """

    def on_mass_extinction_counter_updated(self,
                                           mass_extinction_counter: int,
                                           **kwargs) -> None:
        """ Called right after the mass extinction counter is updated.

        Subclasses should override this method for any actions to run.

        Args:
            mass_extinction_counter (int): Current value of the mass extinction
                counter.
        """

    def on_mass_extinction_start(self, **kwargs) -> None:
        """ Called when at the beginning of a mass extinction event.

        Subclasses should override this method for any actions to run.

        Note:
            When this is called, :meth:`on_reproduction_start()` is not called.
        """

    def on_reproduction_start(self, **kwargs) -> None:
        """ Called at the beginning of the reproductive process.

        Subclasses should override this method for any actions to run.

        Note:
            When this is called, :meth:`on_mass_extinction_start()` is not
            called.
        """

    def on_speciation_start(self, **kwargs) -> None:
        """ Called at the beginning of the speciation process.

        Called after the reproduction or mass extinction have occurred and
        immediately before the speciation process.

        Subclasses should override this method for any actions to run.

        Args:
            invalid_genomes_replaced (int): Number of invalid genomes replaced
                during the reproduction step.
        """

    def on_generation_end(self,
                          current_generation: int,
                          max_generations: int,
                          **kwargs) -> None:
        """ Called at the end of each generation.

        Subclasses should override this method for any actions to run.

        Args:
            current_generation (int): Number of the current generation.
            max_generations (int): Maximum number of generations.
        """

    def on_evolution_end(self, total_generations: int, **kwargs) -> None:
        """ Called when the evolutionary process ends.

        Args:
            total_generations (int): Total number of generations processed
                during the evolutionary process. Might not be the maximum number
                of generations specified by the user, if some sort of early
                stopping occurs.
        """


class CompleteStdOutLogger(Callback):
    """ Callback that prints info to the standard output.

    Note:
        This callback is heavily verbose / wordy! Consider using the reduced
        logger (:class:`SimpleStdOutLogger`) if you don't like too much text on
        your screen.
    """

    _TAB_HEADER = ["NAME", "CURRENT", "PAST", "INCREASE", "INCREASE (%)"]
    SEP_SIZE = 80
    TAB_ARGS = dict(no_borders=False, justify="c", min_column_width=14)

    def __init__(self,
                 colored_text: bool = True,
                 output_cleaner: Optional[Callable] = utils.clear_output):
        super().__init__()
        self.clear_output = output_cleaner
        self.colored_text = colored_text
        self._past_best_fitness = 0.0
        self._past_avg_fitness = 0.0
        self._past_weight_mutation = 0.0
        self._past_weight_perturbation = 0.0
        self._table = None  # type: Optional[List[List[str]]]
        self._timer = 0.0
        self._summary_msg = ""

    def on_generation_start(self,
                            current_generation: int,
                            max_generations: int,
                            **kwargs) -> None:
        self._timer = timer()
        print("\n"
              f"[{(current_generation + 1) / max_generations:.2%}] "
              f"Generation {current_generation + 1} of {max_generations}.\n"
              f". Calculating fitness "
              f"(last: {self._past_best_fitness:.2E})... ", end="")

    def on_fitness_calculated(self,
                              best_fitness: float,
                              avg_fitness: float,
                              **kwargs) -> None:
        print("done!")
        self._table = [
            utils.make_table_row(name="Best fitness",
                                 current=best_fitness,
                                 past=self._past_best_fitness),
            utils.make_table_row(name="Avg population\nfitness",
                                 current=avg_fitness,
                                 past=self._past_avg_fitness)
        ]

        self._past_best_fitness = best_fitness
        self._past_avg_fitness = best_fitness

    def on_mass_extinction_counter_updated(self,
                                           mass_extinction_counter: int,
                                           **kwargs) -> None:
        ct = mass_extinction_counter  # type: Union[int, str]
        ct_max = self.population.config.mass_extinction_threshold

        if self.colored_text:
            pc = ct / ct_max
            ct = style(str(ct), fg=("green" if pc < 0.33
                                    else "yellow" if pc < 0.66
                                    else "red"), bold=(pc >= 0.66))
        print(f". Mass extinction counter: {ct} / {ct_max}")
        self._summary_msg += f". Mass extinction counter: {ct} / {ct_max}"

        weight_mutation = self.population.config.weight_mutation_chance
        weight_perturbation = self.population.config.weight_perturbation_pc
        self._table += [
            utils.make_table_row(name="Weight\nmutation chance",
                                 current=weight_mutation,
                                 past=self._past_weight_mutation,
                                 show_inc_pc=False,
                                 inc_format="+0.2%"),
            utils.make_table_row(name="Weight\nperturbation",
                                 current=weight_perturbation,
                                 past=self._past_weight_perturbation,
                                 show_inc_pc=False,
                                 inc_format="+0.2%")
        ]

        self._past_weight_mutation = weight_mutation
        self._past_weight_perturbation = weight_perturbation

    def on_mass_extinction_start(self, **kwargs) -> None:
        msg = ". Mass extinction in progress... "
        msg = style(msg, fg='red', bold=True) if self.colored_text else msg
        print(f"{msg}", end="")

        msg = '. Mass extinction occurred!'
        msg = style(msg, fg='red', bold=True) if self.colored_text else msg
        self._summary_msg += "\n" + msg

    def on_reproduction_start(self, **kwargs) -> None:
        print(". Reproduction... ", end="")

    def on_speciation_start(self, **kwargs) -> None:
        pass

    def on_generation_end(self,
                          current_generation: int,
                          max_generations: int,
                          **kwargs) -> None:
        print("done!\n")
        if self.clear_output is not None:
            self.clear_output()

        print(f">> GENERATION {current_generation + 1} SUMMARY:")
        if self.clear_output is not None:
            print(self._summary_msg)

        print(f". Processing time: {timer() - self._timer : .4f}s\n")

        print(columnar(self._table,
                       CompleteStdOutLogger._TAB_HEADER,
                       **CompleteStdOutLogger.TAB_ARGS))
        print("#" * CompleteStdOutLogger.SEP_SIZE)
        self._summary_msg = ""

    def on_evolution_end(self, total_generations: int, **kwargs) -> None:
        print(f"Evolution ended after {total_generations + 1} generations.")


class SimpleStdOutLogger(Callback):
    """
    TODO
    """


class History(Callback):
    """ Callback that records events during the evolutionary process.

    TODO
    """

    def __init__(self):
        super().__init__()
        self.history = {
            "best_fitness": [],
            "avg_fitness": [],
            "mass_extinction_counter": [],
            "weight_mutation_chance": [],
            "weight_perturbation_pc": [],
            "mass_extinction_events": [],
            "processing_time": [],
        }  # type: Dict[str, List[Any]]

        self._current_generation = 0
        self._timer = 0.0

    def __getattr__(self, key):
        return self.history[key]

    def _update_history(self, **kwargs):
        for k, v in kwargs.items():
            if k not in self.history:
                self.history[k] = []
            self.history[k].append(v)

    def on_generation_start(self,
                            current_generation: int,
                            max_generations: int,
                            **kwargs) -> None:
        self._timer = timer()
        self._update_history(**kwargs)
        self._current_generation = current_generation

    def on_fitness_calculated(self,
                              best_fitness: float,
                              avg_fitness: float,
                              **kwargs) -> None:
        self._update_history(best_fitness=best_fitness,
                             avg_fitness=avg_fitness,
                             **kwargs)

    def on_mass_extinction_counter_updated(self,
                                           mass_extinction_counter: int,
                                           **kwargs) -> None:
        self._update_history(
            mass_extinction_counter=mass_extinction_counter,
            weight_mutation_chance=self.population.config.weight_mutation_chance,
            weight_perturbation_pc=self.population.config.weight_perturbation_pc,
            **kwargs,
        )

    def on_mass_extinction_start(self, **kwargs) -> None:
        self._update_history(mass_extinction_events=self._current_generation,
                             **kwargs)

    def on_reproduction_start(self, **kwargs) -> None:
        self._update_history(**kwargs)

    def on_speciation_start(self, **kwargs) -> None:
        self._update_history(**kwargs)

    def on_generation_end(self,
                          current_generation: int,
                          max_generations: int,
                          **kwargs) -> None:
        self._update_history(processing_time=timer() - self._timer,
                             **kwargs)

    def on_evolution_end(self, total_generations: int, **kwargs) -> None:
        self._update_history(**kwargs)

    def visualize(self,
                  attrs: Union[Tuple[str, ...], str] = ("best_fitness",
                                                        "avg_fitness"),
                  figsize=(10, 6),
                  log_scale: bool = True) -> None:
        """ Simple utility method for plotting the recorded information.

        This method is a simple wrapper around `matplotlib`. It isn't suited for
        advanced plotting.

        Attributes:
            attrs (Union[Tuple[str, ...], str]): Tuple with the names of the
                attributes to be plotted. If "all", all plottable attributes are
                plotted.
            log_scale (bool): Whether or not to use a logarithmic scale on the
                y-axis.
        """
        generations = range(len(self.history["best_fitness"]))
        if type(attrs) is str and attrs == "all":
            attrs = tuple(self.history.keys())

        plt.figure(figsize=figsize)
        plt.yscale("log" if log_scale else "linear")
        for key in attrs:
            data = self.history[key]
            plt.plot(generations, data, label=key)

        plt.legend()
        plt.show()


class FitnessEarlyStopping(Callback):
    """ Stops the evolution if a given fitness value is achieved.

    This callback is used to halt the evolutionary process when a certain
    fitness value is achieved by the population's best genome for a given number
    of consecutive generations.

    Args:
        fitness_threshold (float): Fitness to be achieved for the evolution to
            stop.
        min_consecutive_generations (int): Number of consecutive generations
            with a fitness equal or higher than ``fitness_threshold`` for the
            early stopping to occur.

    Attributes:
        fitness_threshold (float): Fitness to be achieved for the evolution to
            stop.
        min_consecutive_generations (int): Number of consecutive generations
            with a fitness equal or higher than ``fitness_threshold`` for the
            early stopping to occur.
        stopped_generation (Optional[int]): Generation in which the early
            stopping occurred. `None` if the early stopping never occurred.
    """

    def __init__(self,
                 fitness_threshold: float,
                 min_consecutive_generations: int) -> None:
        super().__init__()
        self.fitness_threshold = fitness_threshold
        self.min_consecutive_generations = min_consecutive_generations
        self.stopped_generation = None  # type: Optional[int]
        self._consec_gens = 0

    def on_fitness_calculated(self,
                              best_fitness: float,
                              avg_fitness: float,
                              **kwargs) -> None:
        if best_fitness >= self.fitness_threshold:
            self._consec_gens += 1
        else:
            self._consec_gens = 0

    def on_generation_end(self,
                          current_generation: int,
                          max_generations: int,
                          **kwargs) -> None:
        if self._consec_gens >= self.min_consecutive_generations:
            self.population.stop_evolving = True
            self.stopped_generation = current_generation


class PopulationCheckpoint(Callback):
    """
    TODO
    """


class BestGenomeCheckpoint(Callback):
    """
    TODO
    """