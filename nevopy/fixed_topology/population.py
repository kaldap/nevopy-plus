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

"""
TODO
"""

from typing import Optional, List, Callable, Sequence, Tuple
import numpy as np

from nevopy.fixed_topology.genomes import FixedTopologyGenome
from nevopy.fixed_topology.config import FixedTopologyConfig
from nevopy.processing.base_scheduler import ProcessingScheduler
from nevopy.processing.ray_processing import RayProcessingScheduler
from nevopy.callbacks import Callback, History, CompleteStdOutLogger
from nevopy.base_population import Population
from nevopy import utils

import logging
_logger = logging.getLogger(__name__)


class FixedTopologyPopulation(Population):
    """
    TODO
    """

    def __init__(self,
                 size: int,
                 base_genome: FixedTopologyGenome,
                 config: Optional[FixedTopologyConfig] = None,
                 processing_scheduler: Optional[ProcessingScheduler] = None,
    ) -> None:
        super().__init__(size)

        # Base genome:
        self._base_genome = base_genome
        if self._base_genome.input_shape is None:
            raise ValueError("The base genome's input shape has not been "
                             "defined! Pass an input shape to the genome's "
                             "constructor or feed a sample input to the "
                             "genome.")

        # Config:
        self._config = config if config is not None else FixedTopologyConfig()

        if (self._base_genome.config is not None
                and self._base_genome.config != self._config):
            raise ValueError("The base genome was assigned a different config "
                             "object than the one used by the population!")

        self._base_genome.config = self._config

        # Processing scheduler:
        self._scheduler = (processing_scheduler
                           if processing_scheduler is not None
                           else RayProcessingScheduler())

        # Basic instance variables:
        self._mass_extinction_counter = 0
        self._past_best_fitness = None  # type: Optional[float]
        self._last_improvement = 0

        self._cached_rank_prob_dist = utils.rank_prob_dist(
            size=self._size,
            coefficient=self._config.rank_prob_dist_coefficient,
        )

        # Initial genomes:
        self.genomes = [self._base_genome.random_copy()
                        for _ in range(self._size)]

    @property
    def config(self):
        return self._config

    def evolve(self,
               generations: int,
               fitness_function: Callable[[FixedTopologyGenome], float],
               callbacks: Optional[List[Callback]] = None,
               verbose: int = 2,
               **kwargs) -> History:
        """ Evolves the population of fixed topology genomes.

        Todo:
            Callbacks.

        Args:
            generations (int): Number of generations for the algorithm to run. A
                generation is completed when all the population's genomes have
                been processed and reproduction and speciation has occurred.
            fitness_function (Callable[[FixedTopologyGenome], float]): Fitness
                function to be used to evaluate the fitness of individual
                genomes. It must receive a genome as input and produce a float
                (the genome's fitness) as output.
            callbacks (Optional[List[Callback]]): List with instances of
                :class:`.Callback` that will be called during the evolutionary
                session. By default, a :class:`.History` callback is always
                included in the list. A :class:`.CompleteStdOutLogger` or a
                :class:`.SimpleStdOutLogger` might also be included, depending
                on the value passed to the `verbose` param.
            verbose (int): Verbose level (logging on stdout). Options: 0 (no
                verbose), 1 (light verbose) and 2 (heavy verbose). TODO

        Returns:
            A :class:`.History` object containing useful information recorded
            during the evolutionary process.
        """
        # Preparing callbacks:
        if callbacks is None:
            callbacks = []

        history_callback = History()
        callbacks.append(history_callback)

        if verbose >= 2:
            callbacks.append(CompleteStdOutLogger())
        # elif verbose == 1:
        #     callbacks.append(SimpleStdOutLogger())

        for cb in callbacks:
            cb.population = self

        # Resetting improvement records:
        self._last_improvement = 0
        self._past_best_fitness = float("-inf")

        ############################### Evolving ###############################
        self.stop_evolving = False
        generation_num = 0
        for generation_num in range(generations):
            # CALLBACK: on_generation_start
            for cb in callbacks:
                cb.on_generation_start(generation_num, generations)

            # Calculating and assigning FITNESS:
            fitness_results = self._scheduler.run(
                items=self.genomes,
                func=fitness_function
            )  # type: Sequence[float]

            for genome, fitness in zip(self.genomes, fitness_results):
                genome.fitness = fitness

            best = self.fittest()

            # CALLBACK: on_fitness_calculated
            avg_fitness = self.average_fitness()
            for cb in callbacks:
                cb.on_fitness_calculated(best_fitness=best.fitness,
                                         avg_fitness=avg_fitness)

            # Checking if fitness improved:
            improv_diff = best.fitness - self._past_best_fitness
            improv_min_pc = self._config.maex_improvement_threshold_pc

            if improv_diff >= abs(self._past_best_fitness * improv_min_pc):
                self._mass_extinction_counter = 0
                self._past_best_fitness = best.fitness
            else:
                self._mass_extinction_counter += 1

            self._config.update_mass_extinction(self._mass_extinction_counter)

            # CALLBACK: on_mass_extinction_counter_updated
            for cb in callbacks:
                cb.on_mass_extinction_counter_updated(
                    self._mass_extinction_counter
                )

            # Checking mass extinction:
            preys = 0
            if (self._mass_extinction_counter
                    >= self._config.mass_extinction_threshold):
                # CALLBACK: on_mass_extinction_start
                for cb in callbacks:
                    cb.on_mass_extinction_start()

                # MASS EXTINCTION:
                # The whole population (except for the best genome) is replaced
                # by new random genomes.
                self._mass_extinction_counter = 0
                self.genomes = [best] + [self._base_genome.random_copy()
                                         for _ in range(self._size - 1)]
                assert len(self.genomes) == self.size, ("The number of genomes "
                                                        "doesn't match the "
                                                        "population's size!")
            # REPRODUCTION:
            else:
                # CALLBACK: on_reproduction_start
                for cb in callbacks:
                    cb.on_reproduction_start()

                preys = self.reproduction()

            # CALLBACK: on_generation_end
            for cb in callbacks:
                cb.on_generation_end(generation_num, generations, preys=preys)

            # Checking for early stopping:
            if self.stop_evolving:
                break

        ########################################################################

        # CALLBACK: on_evolution_end
        for cb in callbacks:
            cb.on_evolution_end(generation_num)

        return history_callback

    @staticmethod
    def generate_offspring(args: Tuple[FixedTopologyGenome,
                                       Optional[FixedTopologyGenome], bool],
    ) -> FixedTopologyGenome:
        """ TODO

        Args:
            args:

        Returns:

        """
        p1, p2, predate = args

        # Predatism:
        if predate:
            return p1.random_copy()

        # Mating (sexual) vs Binary fission (asexual):
        baby = p1.mate(p2) if p2 is not None else p1.deep_copy()

        # Mutation:
        if p2 is None or utils.chance(baby.config.weight_mutation_chance):
            baby.mutate_weights()

        return baby

    def reproduction(self) -> int:
        """ Handles the reproduction of the population's genomes.

        TODO

        Returns:
            Number of predated individuals (replaced by a random genome).
        """
        new_pop = []  # type: List[FixedTopologyGenome]
        self.genomes.sort(key=lambda genome: genome.fitness,
                          reverse=True)

        # DEBUG:
        _logger.debug(f"[REPRODUCTION] Sorted genomes ({len(self.genomes)}): "
                      f"{[g.fitness for g in self.genomes]}")

        # Elitism:
        # (preserves the fittest genomes)
        for i in range(min(self._config.elitism_count, self._size)):
            new_pop.append(self.genomes[i])

        # DEBUG:
        _logger.debug(f"[REPRODUCTION] Preserved genomes ({len(new_pop)}): "
                      f"{[g.fitness for g in new_pop]}")

        # Reverse elitism:
        # (excludes the least fit genomes)
        rmv_count = int(self._config.weak_genomes_removal_pc * self._size)
        if rmv_count > 0:
            self.genomes = self.genomes[:-rmv_count]

        # DEBUG:
        _logger.debug(f"[REPRODUCTION] Sorted genomes after reverse elitism "
                      f"({len(self.genomes)}): "
                      f"{[g.fitness for g in self.genomes]}")

        # Choosing mating partners:
        offspring_count = self.size - len(new_pop)
        parents1 = np.random.choice(
            self.genomes,
            size=offspring_count,
            p=self._cached_rank_prob_dist[:len(self.genomes)],
        )

        mating_chance = self._config.mating_chance
        parents2 = np.random.choice(
            # If `None`, only parent 1 will be considered (asexual reproduction)
            [None] + self.genomes,  # type: ignore
            size=offspring_count,
            p=([1 - mating_chance]
               + [mating_chance / len(self.genomes)] * len(self.genomes)),
        )

        # DEBUG:
        # noinspection PyUnresolvedReferences, PyComparisonWithNone
        asexual_count = (parents2 == None).sum()
        _logger.debug(
            f"[REPRODUCTION] Mating: "
            f"{(offspring_count - asexual_count) / offspring_count:0.2%} | "
            f"Binary fission: {asexual_count / offspring_count:0.2%}"
        )

        # Selecting prey:
        # (some of the new genomes will be randomly generated instead of being
        # born through reproduction)
        predatism_chance = self._config.predatism_chance
        predate = np.random.choice([True, False],
                                   size=offspring_count,
                                   p=[predatism_chance, 1 - predatism_chance])

        # DEBUG
        _logger.debug(f"[REPRODUCTION] Preys (predatism): {predate.sum()}")

        # Generating offspring:
        # todo: is this worth parallelizing?
        babies = self._scheduler.run(
            items=[(p1, p2, False) if not predate[i] else (p1, None, True)
                   for i, (p1, p2) in enumerate(zip(parents1, parents2))],
            func=FixedTopologyPopulation.generate_offspring,
        )

        new_pop += babies
        self.genomes = new_pop

        assert len(self.genomes) == self.size, ("The number of genomes doesn't "
                                                "match the population's size!")
        return predate.sum()


