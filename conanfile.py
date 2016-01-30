from conans import ConanFile
import os
import cStringIO


class CppMicroServicesConan(ConanFile):
    name = 'CppMicroServices'
    version = '3.0.0'
    settings = ['os', 'compiler', 'build_type', 'arch']
    generators = ['cmake']
    url = 'https://github.com/azriel91/CppMicroServices-conan.git'
    options = {
        'US_ENABLE_AUTOLOADING_SUPPORT': ['ON', 'OFF'],  # Enable bundle auto-loading support
        'US_ENABLE_THREADING_SUPPORT': ['ON', 'OFF'],    # Enable threading support
        'US_ENABLE_DEBUG_OUTPUT': ['ON', 'OFF'],         # Enable debug messages
        'US_BUILD_SHARED_LIBS': ['ON', 'OFF'],           # Build shared libraries
        'US_BUILD_TESTING': ['ON', 'OFF'],               # Build tests
        'US_BUILD_EXAMPLES': ['ON', 'OFF'],              # Build example projects
    }
    default_options = ('US_ENABLE_AUTOLOADING_SUPPORT=OFF',
                       'US_ENABLE_THREADING_SUPPORT=OFF',
                       'US_ENABLE_DEBUG_OUTPUT=OFF',
                       'US_BUILD_SHARED_LIBS=ON',
                       'US_BUILD_TESTING=OFF',
                       'US_BUILD_EXAMPLES=OFF')
    cppmicroservices_bundles = ['core', 'httpservice', 'shellservice', 'webconsole']
    build_dir = 'build'
    linked_libraries_filename = 'cppmicroservices_linked_libraries.txt'

    def source(self):
        cppmicroservices_url = 'https://github.com/CppMicroServices/CppMicroServices.git'
        beta_branch = 'beta-release-{version}'.format(version=self.version)
        self.run("git clone {url} --branch {branch} --depth 1".format(url=cppmicroservices_url, branch=beta_branch))

    def build(self):
        if not os.path.isdir(self.name):
            self.source()
        option_defines = ' '.join("-D%s=%s" % (option, val) for (option, val) in self.options.iteritems())
        self.run("cmake {src_dir} -B{build_dir} {defines}".format(src_dir=self.name,
                                                                  build_dir=self.build_dir,
                                                                  defines=option_defines))
        self.run("cmake --build {build_dir}".format(build_dir=self.build_dir))

        linked_libraries_file_path = "{conan_dir}/{build_dir}/{filename}".format(conan_dir=self.conanfile_directory,
                                                                                 build_dir=self.build_dir,
                                                                                 filename=self.linked_libraries_filename)
        with open(linked_libraries_file_path, 'w') as linked_libraries_file:
            linked_libraries_file.write('\n'.join(self._get_linker_libraries()))
            linked_libraries_file.close()

    def package(self):
        # Module headers
        for bundle in self.cppmicroservices_bundles:
            # we copy headers from the src path as well because some of the public headers need these to compile
            src_path = "{src_dir}/{bundle}/src".format(src_dir=self.name, bundle=bundle)

            include_path = "{bundle}/include".format(bundle=bundle)
            src_include_path = "{src_dir}/{path}".format(src_dir=self.name, path=include_path)
            build_include_path = "{build_dir}/{path}".format(build_dir=self.build_dir, path=include_path)

            self.copy('*.h', dst=include_path, src=src_path)
            self.copy('*.h', dst=include_path, src=src_include_path)
            self.copy('*.h', dst=include_path, src=build_include_path)

        # Third party headers
        self.copy('*.h', dst='third_party', src="{src_dir}/third_party".format(src_dir=self.name))

        # Generated global includes
        build_include_path = "{build_dir}/include".format(build_dir=self.build_dir)
        self.copy('*.h', dst='include', src=build_include_path)

        # Built artifacts
        build_lib_dir = "{build_dir}/lib".format(build_dir=self.build_dir)
        self.copy('*.so*', dst='lib', src=build_lib_dir)  # In unix systems, the version number is appended
        self.copy('*.a', dst='lib', src=build_lib_dir)
        # msvc places '.lib' files under the build type (Debug/Release) subdirectory
        self.copy('*.lib', dst='lib', src=build_lib_dir, keep_path=False)

        # usWebConsole is built in the bin/main directory, need to check why
        # In unix systems, the version number is appended to the shared library
        self.copy('*.so*', dst='lib', src="{build_dir}/bin/main".format(build_dir=self.build_dir))
        self.copy('*.dll', dst='lib', src="{build_dir}/bin".format(build_dir=self.build_dir))

        # CMake info
        self.copy('CppMicroServicesConfig.cmake', dst='.', src=self.build_dir)
        self.copy('CppMicroServicesConfigVersion.cmake', dst='.', src=self.build_dir)
        self.copy('CppMicroServicesTargets.cmake', dst='.', src=self.build_dir)

        # CMake functions
        # We need to copy '*' because there are also template code files in the cmake directory
        self.copy('*', dst='cmake', src="{src_dir}/cmake".format(src_dir=self.name))

        # Linked libraries file
        self.copy(self.linked_libraries_filename, dst='.', src=self.build_dir)

    def package_info(self):
        """ Maybe we shouldn't link to every bundle that is built, and just link to the CppMicroServices one """
        # linked_libraries_file_path = "%s/%s" % (self.cpp_info.rootpath, self.linked_libraries_filename)
        # with open(linked_libraries_file_path, 'r') as linked_libraries_file:
        #     # Warning: This reads the whole file into memory, but we expect it to be small
        #     self.cpp_info.libs = linked_libraries_file.read().split()
        self.cpp_info.libs = ['CppMicroServices']
        if self.settings.os == 'Linux':
            self.cpp_info.libs += ['dl']

        self.cpp_info.includedirs += ["{bundle}/include".format(bundle=bundle)
                                      for bundle in self.cppmicroservices_bundles]

        # The self.copy function used in package recursively copies files under subdirectories, but includes the full
        # path. For header includes to work, either the subdirectory paths must not be included when copying, or we add
        # the subdirectories as directories on the compilation include paths
        #
        # Private headers under 'core/src/**' that were copied into 'core/include/**'
        # Improvement: recursively include any directories underneath {bundle}/include
        self.cpp_info.includedirs += ["core/include/{core_private}".format(core_private=sub_dir)
                                      for sub_dir in ['bundle', 'service', 'util']]

    def _get_linker_libraries(self):
        # Extract dependencies for the CppMicroServices library, to be appended to self.cpp_info.libs
        # See http://stackoverflow.com/a/31940106/1576773
        self.run("cmake --graphviz={build_dir}/cppmicroservices.dot {build_dir}".format(build_dir=self.build_dir), False)

        dependencies = None
        try:
            output_deps = cStringIO.StringIO()
            command = "sed -n 's/.*label=\"\\(.*\\)\"\\s.*/\\1/p' {build_dir}/cppmicroservices.dot.{lib}".format(build_dir=self.build_dir,
                                                                                                                 lib=self.name)
            self.run(command, output_deps)
            dependencies = output_deps.getvalue().split()
        finally:
            output_deps.close()
            self.run("rm -f {build_dir}/cppmicroservices.dot*".format(build_dir=self.build_dir))
        return dependencies
